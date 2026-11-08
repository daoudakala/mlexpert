"""Règles métier du module dashboards.

`ServiceReporting` : construit avec `(db, entreprise_id)`. Contrairement
aux autres services, il ne modifie jamais rien — trois méthodes de
lecture pure, chacune retournant des dataclasses (pas de modèles
SQLAlchemy à gérer, voir `repository.py`).

Toujours filtré sur les écritures VALIDÉES uniquement (voir
`repository.py`) : une balance, un grand livre ou un résultat ne
reflètent jamais un brouillon.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.dashboards.repository import RepositoryReporting
from app.modules.exercices.models import Exercice
from app.modules.exercices.repository import RepositoryExercice
from app.modules.tiers.models import Tiers

# Même horizon que `notifications/alertes.py` pour les clôtures à venir
# (cahier, section 24) — un exercice qui apparaît dans l'alerte doit aussi
# apparaître dans ce compteur, par cohérence entre les deux écrans.
JOURS_CLOTURE_PROCHE = 30

CLASSE_CHARGES = 6
CLASSE_PRODUITS = 7
CLASSE_HAO = 8

# Bornes des tranches d'ancienneté de la balance âgée (cahier, section
# 13.3 "Échéances dépassées") — en jours de retard sur la date d'échéance.
# Les lignes sans date d'échéance connue (`Tiers.delai_paiement_jours` non
# renseigné ET pas de date explicite) vont dans leur propre tranche
# plutôt que d'être arbitrairement classées : voir `TrancheAgee.inconnue`.
BORNES_TRANCHES = (30, 60, 90)


@dataclass
class LigneBalance:
    compte_id: uuid.UUID
    numero: str
    libelle: str
    total_debit: Decimal
    total_credit: Decimal
    solde: Decimal


@dataclass
class LigneGrandLivre:
    ligne_ecriture_id: uuid.UUID
    date_ecriture: date
    ecriture_id: uuid.UUID
    numero_ecriture: str | None
    libelle: str
    debit: Decimal
    credit: Decimal
    solde_progressif: Decimal


@dataclass
class LigneBalanceComparee:
    compte_id: uuid.UUID
    numero: str
    libelle: str
    solde_n: Decimal
    solde_n1: Decimal | None
    variation_montant: Decimal | None
    variation_pourcentage: float | None


@dataclass
class CompteResultatSommaire:
    exercice_id: uuid.UUID
    total_charges: Decimal
    total_produits: Decimal
    resultat_net: Decimal


@dataclass
class Bilan:
    """Cahier, section 9 "Module états financiers". Calculé par rubrique
    (pas poste par poste au sens strict de la liasse SYSCOHADA officielle
    — voir la note de `ServiceReporting.bilan`), directement à partir des
    soldes par compte de l'exercice (même agrégat que `balance_generale`),
    aucune donnée supplémentaire persistée."""

    exercice_id: uuid.UUID
    immobilisations: Decimal
    stocks: Decimal
    creances: Decimal
    tresorerie_actif: Decimal
    total_actif: Decimal
    ressources_durables: Decimal
    dettes_circulantes: Decimal
    tresorerie_passif: Decimal
    total_passif: Decimal
    equilibre: bool


@dataclass
class CompteResultatDetaille:
    """Étend `CompteResultatSommaire` avec la décomposition SYSCOHADA
    exploitation / financier / HAO (voir `ServiceReporting.compte_resultat_detaille`
    pour la simplification retenue sur le HAO)."""

    exercice_id: uuid.UUID
    total_charges_exploitation: Decimal
    total_produits_exploitation: Decimal
    resultat_exploitation: Decimal
    total_charges_financieres: Decimal
    total_produits_financiers: Decimal
    resultat_financier: Decimal
    resultat_activites_ordinaires: Decimal
    total_charges_hao: Decimal
    total_produits_hao: Decimal
    resultat_hao: Decimal
    resultat_net: Decimal


@dataclass
class LigneEcheance:
    ligne_ecriture_id: uuid.UUID
    ecriture_id: uuid.UUID
    numero_ecriture: str | None
    date_ecriture: date
    tiers_id: uuid.UUID
    code_tiers: str
    raison_sociale_tiers: str
    libelle: str
    montant: Decimal  # débit - crédit : positif = somme due par ce tiers (client) ou à ce tiers (fournisseur)
    date_echeance: date | None
    jours_retard: int | None  # None si date_echeance inconnue ; négatif si pas encore échue


@dataclass
class TableauDirection:
    """Cahier, section 22 "Tableaux de bord — Direction". Pure agrégation
    de données déjà calculées ailleurs (`echeancier`, `balance_generale`,
    `compte_resultat_detaille`) — aucun nouveau modèle, même logique que
    le tableau de bord client de l'Étape 4. `exercice_id` est `None` (et
    `resultat_net_exercice`/`tresorerie_disponible` restent à zéro ou
    `None`) si l'entreprise n'a encore aucun exercice ouvert ni passé
    couvrant aujourd'hui — pas une erreur, une entreprise peut être
    enregistrée avant son premier exercice."""

    exercice_id: uuid.UUID | None
    tresorerie_disponible: Decimal
    creances_clients_ouvertes: Decimal
    dettes_fournisseurs_ouvertes: Decimal
    echeances_clients_en_retard: int
    echeances_fournisseurs_en_retard: int
    resultat_net_exercice: Decimal | None


@dataclass
class LignePrevisionTresorerie:
    """Une ligne de la courbe de prévision (cahier, section 12
    "Prévision de trésorerie") : une échéance ouverte (client =
    encaissement, fournisseur = décaissement), positionnée dans le temps
    et cumulée sur le solde de trésorerie actuel."""

    date_echeance: date
    libelle: str
    montant: Decimal  # signé : positif = encaissement, négatif = décaissement
    solde_cumule: Decimal


@dataclass
class PrevisionTresorerie:
    """Cahier, section 12. Projette le solde de trésorerie ACTUEL (même
    calcul que `TableauDirection.tresorerie_disponible`) en y ajoutant,
    jour par jour, les échéances clients/fournisseurs déjà ouvertes dont
    la date d'échéance tombe dans l'horizon demandé — aucune hypothèse
    sur des opérations futures non encore enregistrées, uniquement ce qui
    est déjà en base (écritures validées non lettrées avec échéance
    connue).

    Les échéances SANS date connue ne peuvent pas être placées sur la
    courbe (on ne sait pas quand l'encaissement/décaissement aura lieu) :
    leur montant total est exposé à part plutôt que silencieusement omis,
    pour que le cabinet sache que la projection est incomplète sur ce
    point."""

    solde_actuel: Decimal
    horizon_jours: int
    lignes: list[LignePrevisionTresorerie]
    solde_final_projete: Decimal
    montant_sans_echeance_clients: Decimal
    montant_sans_echeance_fournisseurs: Decimal


@dataclass
class TableauComptabilite:
    """Cahier, section 22 "Tableaux de bord — Comptabilité". Pas
    d'indicateur "anomalies" (aucune notion équivalente dans ce projet,
    omis plutôt que de fabriquer une métrique) ; "rapprochements en
    attente" est représenté par `lignes_bancaires_non_lettrees` (voir
    `RepositoryReporting.compter_lignes_bancaires_non_lettrees`)."""

    ecritures_brouillon: int
    lignes_bancaires_non_lettrees: int
    clotures_a_venir: int
    demandes_non_traitees: int


@dataclass
class TrancheAgee:
    tiers_id: uuid.UUID
    code_tiers: str
    raison_sociale_tiers: str
    non_echu: Decimal
    jours_0_30: Decimal
    jours_31_60: Decimal
    jours_61_90: Decimal
    jours_plus_90: Decimal
    echeance_inconnue: Decimal
    total: Decimal


class ServiceReporting:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.reporting = RepositoryReporting(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)

    def balance_generale(self, exercice_id: uuid.UUID) -> list[LigneBalance]:
        self._obtenir_exercice_ou_lever(exercice_id)
        return [
            LigneBalance(
                compte_id=compte_id,
                numero=numero,
                libelle=libelle,
                total_debit=total_debit,
                total_credit=total_credit,
                solde=total_debit - total_credit,
            )
            for compte_id, numero, libelle, _classe, total_debit, total_credit in self.reporting.totaux_par_compte(
                exercice_id
            )
        ]

    def balance_comparee_n1(self, exercice_id: uuid.UUID) -> list[LigneBalanceComparee]:
        """Balance générale de l'exercice ET de son exercice précédent
        (`Exercice.exercice_precedent_id`), compte par compte (cahier,
        section 7.2 "comparaison N / N-1").

        Un compte présent dans un seul des deux exercices apparaît quand
        même, avec un solde à zéro pour l'exercice où il n'a aucun
        mouvement — plutôt que de l'omettre, ce qui masquerait un compte
        soldé entre N-1 et N (ou ouvert cette année).

        Si l'exercice n'a pas d'exercice précédent renseigné,
        `solde_n1`/`variation_*` valent `None` (pas de donnée à comparer),
        plutôt qu'une erreur : un premier exercice n'a simplement rien à
        comparer, ce n'est pas une situation invalide.
        """
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        balance_n = {ligne.compte_id: ligne for ligne in self.balance_generale(exercice_id)}
        balance_n1 = (
            {ligne.compte_id: ligne for ligne in self.balance_generale(exercice.exercice_precedent_id)}
            if exercice.exercice_precedent_id is not None
            else {}
        )

        lignes = []
        for compte_id in set(balance_n) | set(balance_n1):
            ligne_n = balance_n.get(compte_id)
            ligne_n1 = balance_n1.get(compte_id)
            reference = ligne_n or ligne_n1  # l'un des deux existe forcément

            solde_n = ligne_n.solde if ligne_n is not None else Decimal("0")
            if exercice.exercice_precedent_id is None:
                solde_n1 = None
            else:
                solde_n1 = ligne_n1.solde if ligne_n1 is not None else Decimal("0")

            variation_montant = solde_n - solde_n1 if solde_n1 is not None else None
            variation_pourcentage = None
            if solde_n1 is not None and solde_n1 != 0:
                variation_pourcentage = float(variation_montant / abs(solde_n1) * 100)

            lignes.append(
                LigneBalanceComparee(
                    compte_id=compte_id,
                    numero=reference.numero,
                    libelle=reference.libelle,
                    solde_n=solde_n,
                    solde_n1=solde_n1,
                    variation_montant=variation_montant,
                    variation_pourcentage=variation_pourcentage,
                )
            )
        lignes.sort(key=lambda l: l.numero)
        return lignes

    def grand_livre(self, compte_id: uuid.UUID, exercice_id: uuid.UUID) -> list[LigneGrandLivre]:
        self._obtenir_exercice_ou_lever(exercice_id)
        if self.comptes.obtenir(compte_id) is None:
            raise RessourceIntrouvable("Compte introuvable.")

        lignes = []
        solde_progressif = Decimal("0")
        for (
            ligne_id,
            date_ecriture,
            ecriture_id,
            numero_ecriture,
            libelle_ligne,
            libelle_ecriture,
            debit,
            credit,
        ) in self.reporting.lignes_grand_livre(compte_id, exercice_id):
            solde_progressif += debit - credit
            lignes.append(
                LigneGrandLivre(
                    ligne_ecriture_id=ligne_id,
                    date_ecriture=date_ecriture,
                    ecriture_id=ecriture_id,
                    numero_ecriture=numero_ecriture,
                    libelle=libelle_ligne or libelle_ecriture,
                    debit=debit,
                    credit=credit,
                    solde_progressif=solde_progressif,
                )
            )
        return lignes

    def compte_resultat_sommaire(self, exercice_id: uuid.UUID) -> CompteResultatSommaire:
        self._obtenir_exercice_ou_lever(exercice_id)
        totaux = self.reporting.totaux_par_classe(exercice_id, (CLASSE_CHARGES, CLASSE_PRODUITS))

        debit_charges, credit_charges = totaux.get(CLASSE_CHARGES, (Decimal("0"), Decimal("0")))
        debit_produits, credit_produits = totaux.get(CLASSE_PRODUITS, (Decimal("0"), Decimal("0")))
        # Une charge (classe 6) est normalement débitrice : son solde net
        # est (débit - crédit) ; un produit (classe 7) est normalement
        # créditeur : son solde net est (crédit - débit).
        total_charges = debit_charges - credit_charges
        total_produits = credit_produits - debit_produits

        return CompteResultatSommaire(
            exercice_id=exercice_id,
            total_charges=total_charges,
            total_produits=total_produits,
            resultat_net=total_produits - total_charges,
        )

    def bilan(self, exercice_id: uuid.UUID) -> Bilan:
        """Cahier, section 9. Classement par RUBRIQUE (pas par poste
        officiel de la liasse SYSCOHADA — le cahier lui-même liste le
        "référentiel comptable exact" et les "modèles d'états financiers
        définitifs" parmi les points encore à valider, section 35.2) :
        - classe 2 (immobilisations, déjà nette des amortissements classe
          28 qui sont contra, donc soustraits automatiquement dans le
          solde) et classe 3 (stocks) vont entièrement à l'actif ;
        - classe 4 et classe 5 sont réparties par le SIGNE du solde de
          chaque compte (débiteur -> actif, créditeur -> passif), pas par
          une liste de comptes : un compte normalement débiteur qui
          termine créditeur (ex. client qui a trop payé) bascule bien
          côté passif, et réciproquement ;
        - classe 1 (normalement créditrice) va en ressources durables, à
          laquelle s'ajoute le résultat net de l'exercice EN COURS tel que
          `compte_resultat_sommaire` le calcule : tant que l'exercice
          n'est pas clôturé, ce résultat n'est pas encore comptabilisé en
          classe 1, mais doit déjà figurer au bilan pour qu'il s'équilibre.
        """
        self._obtenir_exercice_ou_lever(exercice_id)

        immobilisations = Decimal("0")
        stocks = Decimal("0")
        creances = Decimal("0")
        tresorerie_actif = Decimal("0")
        ressources_durables = Decimal("0")
        dettes_circulantes = Decimal("0")
        tresorerie_passif = Decimal("0")

        for _compte_id, _numero, _libelle, classe, debit, credit in self.reporting.totaux_par_compte(exercice_id):
            solde = debit - credit
            if classe == 2:
                immobilisations += solde
            elif classe == 3:
                stocks += solde
            elif classe == 4:
                if solde > 0:
                    creances += solde
                else:
                    dettes_circulantes += -solde
            elif classe == 5:
                if solde > 0:
                    tresorerie_actif += solde
                else:
                    tresorerie_passif += -solde
            elif classe == 1:
                ressources_durables += -solde
            # Classes 6, 7, 8 : hors bilan (voir compte_resultat_detaille).

        ressources_durables += self.compte_resultat_detaille(exercice_id).resultat_net

        total_actif = immobilisations + stocks + creances + tresorerie_actif
        total_passif = ressources_durables + dettes_circulantes + tresorerie_passif

        return Bilan(
            exercice_id=exercice_id,
            immobilisations=immobilisations,
            stocks=stocks,
            creances=creances,
            tresorerie_actif=tresorerie_actif,
            total_actif=total_actif,
            ressources_durables=ressources_durables,
            dettes_circulantes=dettes_circulantes,
            tresorerie_passif=tresorerie_passif,
            total_passif=total_passif,
            equilibre=(total_actif == total_passif),
        )

    def compte_resultat_detaille(self, exercice_id: uuid.UUID) -> CompteResultatDetaille:
        """Décomposition SYSCOHADA exploitation / financier / HAO.
        Exploitation vs financier se distingue par le NUMÉRO de compte
        (les comptes `67x`/`77x` sont réservés par convention SYSCOHADA
        aux charges/produits financiers, dans les classes 6/7 qui sont
        sinon entièrement "exploitation"). Le HAO (classe 8), en
        revanche, est classé par le SIGNE du solde (débiteur = charge,
        créditeur = produit) plutôt que par une liste de sous-comptes
        officiels (81/82/83...) que je ne veux pas deviner — simplification
        à affiner si la liste exacte des comptes HAO utilisés est fournie."""
        self._obtenir_exercice_ou_lever(exercice_id)

        charges_exploitation = Decimal("0")
        produits_exploitation = Decimal("0")
        charges_financieres = Decimal("0")
        produits_financiers = Decimal("0")
        charges_hao = Decimal("0")
        produits_hao = Decimal("0")

        for _compte_id, numero, _libelle, classe, debit, credit in self.reporting.totaux_par_compte(exercice_id):
            if classe == CLASSE_CHARGES:
                if numero.startswith("67"):
                    charges_financieres += debit - credit
                else:
                    charges_exploitation += debit - credit
            elif classe == CLASSE_PRODUITS:
                if numero.startswith("77"):
                    produits_financiers += credit - debit
                else:
                    produits_exploitation += credit - debit
            elif classe == CLASSE_HAO:
                solde = debit - credit
                if solde > 0:
                    charges_hao += solde
                else:
                    produits_hao += -solde

        resultat_exploitation = produits_exploitation - charges_exploitation
        resultat_financier = produits_financiers - charges_financieres
        resultat_activites_ordinaires = resultat_exploitation + resultat_financier
        resultat_hao = produits_hao - charges_hao

        return CompteResultatDetaille(
            exercice_id=exercice_id,
            total_charges_exploitation=charges_exploitation,
            total_produits_exploitation=produits_exploitation,
            resultat_exploitation=resultat_exploitation,
            total_charges_financieres=charges_financieres,
            total_produits_financiers=produits_financiers,
            resultat_financier=resultat_financier,
            resultat_activites_ordinaires=resultat_activites_ordinaires,
            total_charges_hao=charges_hao,
            total_produits_hao=produits_hao,
            resultat_hao=resultat_hao,
            resultat_net=resultat_activites_ordinaires + resultat_hao,
        )

    def echeancier(self, type_tiers: str, *, aujourd_hui: date | None = None) -> list[LigneEcheance]:
        """Lignes non lettrées (ouvertes) d'un côté du cycle tiers
        (cahier, section 8.4 "Échéanciers clients/fournisseurs") —
        volontairement PAS filtré par exercice : une facture impayée reste
        ouverte au-delà de la clôture de l'exercice qui l'a vue naître.

        `montant` est toujours le montant RESTANT DÛ dans le sens naturel
        du rôle — positif pour une facture, négatif pour un avoir/trop-
        perçu non encore imputé — jamais le débit-crédit brut : un client
        doit normalement au débit (montant = débit - crédit), un
        fournisseur est dû au crédit (montant = crédit - débit), même
        logique de signe que `compte_resultat_sommaire` pour les
        produits."""
        colonne = self._colonne_compte_collectif(type_tiers)
        aujourd_hui = aujourd_hui or date.today()
        signe = 1 if type_tiers == "client" else -1

        lignes = []
        for (
            ligne_id,
            date_ecriture,
            ecriture_id,
            numero_ecriture,
            libelle_ecriture,
            tiers_id,
            code_tiers,
            raison_sociale,
            libelle_ligne,
            debit,
            credit,
            date_echeance,
        ) in self.reporting.lignes_echeancier(colonne_compte_collectif=colonne):
            jours_retard = (aujourd_hui - date_echeance).days if date_echeance is not None else None
            lignes.append(
                LigneEcheance(
                    ligne_ecriture_id=ligne_id,
                    ecriture_id=ecriture_id,
                    numero_ecriture=numero_ecriture,
                    date_ecriture=date_ecriture,
                    tiers_id=tiers_id,
                    code_tiers=code_tiers,
                    raison_sociale_tiers=raison_sociale,
                    libelle=libelle_ligne or libelle_ecriture,
                    montant=signe * (debit - credit),
                    date_echeance=date_echeance,
                    jours_retard=jours_retard,
                )
            )
        return lignes

    def balance_agee(self, type_tiers: str, *, aujourd_hui: date | None = None) -> list[TrancheAgee]:
        """Regroupe `echeancier(...)` par tiers et par tranche d'ancienneté
        (cahier, section 13.3). Une ligne sans date d'échéance connue va
        dans `echeance_inconnue`, jamais arbitrairement dans une tranche
        de retard — voir la note de tête de fichier sur `BORNES_TRANCHES`."""
        tranches: dict[uuid.UUID, TrancheAgee] = {}
        for ligne in self.echeancier(type_tiers, aujourd_hui=aujourd_hui):
            tranche = tranches.get(ligne.tiers_id)
            if tranche is None:
                tranche = TrancheAgee(
                    tiers_id=ligne.tiers_id,
                    code_tiers=ligne.code_tiers,
                    raison_sociale_tiers=ligne.raison_sociale_tiers,
                    non_echu=Decimal("0"),
                    jours_0_30=Decimal("0"),
                    jours_31_60=Decimal("0"),
                    jours_61_90=Decimal("0"),
                    jours_plus_90=Decimal("0"),
                    echeance_inconnue=Decimal("0"),
                    total=Decimal("0"),
                )
                tranches[ligne.tiers_id] = tranche

            if ligne.jours_retard is None:
                tranche.echeance_inconnue += ligne.montant
            elif ligne.jours_retard < 0:
                tranche.non_echu += ligne.montant
            elif ligne.jours_retard <= BORNES_TRANCHES[0]:
                tranche.jours_0_30 += ligne.montant
            elif ligne.jours_retard <= BORNES_TRANCHES[1]:
                tranche.jours_31_60 += ligne.montant
            elif ligne.jours_retard <= BORNES_TRANCHES[2]:
                tranche.jours_61_90 += ligne.montant
            else:
                tranche.jours_plus_90 += ligne.montant
            tranche.total += ligne.montant

        return sorted(tranches.values(), key=lambda t: t.code_tiers)

    def _tresorerie_disponible(self, exercice: Exercice | None) -> Decimal:
        """Solde de trésorerie actuel : solde comptable (classe 5) de
        chaque compte bancaire actif, sur l'exercice couvrant la date de
        référence. `None` si aucun exercice ne couvre cette date (voir
        `_exercice_courant`) — une entreprise peut être enregistrée avant
        son premier exercice, ce n'est pas une erreur.

        Partagé par `tableau_direction` et `prevision_tresorerie` : les
        deux partent du même solde actuel avant de diverger (l'un
        l'affiche tel quel, l'autre le projette dans le temps)."""
        if exercice is None:
            return Decimal("0")
        soldes_par_compte = {ligne.compte_id: ligne.solde for ligne in self.balance_generale(exercice.id)}
        tresorerie_disponible = Decimal("0")
        for compte_comptable_id, solde_initial in self.reporting.comptes_bancaires_actifs():
            tresorerie_disponible += solde_initial + soldes_par_compte.get(compte_comptable_id, Decimal("0"))
        return tresorerie_disponible

    def tableau_direction(self, *, aujourd_hui: date | None = None) -> TableauDirection:
        aujourd_hui = aujourd_hui or date.today()
        exercice = self._exercice_courant(aujourd_hui)

        tresorerie_disponible = self._tresorerie_disponible(exercice)
        resultat_net_exercice: Decimal | None = None
        if exercice is not None:
            resultat_net_exercice = self.compte_resultat_detaille(exercice.id).resultat_net

        lignes_clients = self.echeancier("client", aujourd_hui=aujourd_hui)
        lignes_fournisseurs = self.echeancier("fournisseur", aujourd_hui=aujourd_hui)

        return TableauDirection(
            exercice_id=exercice.id if exercice is not None else None,
            tresorerie_disponible=tresorerie_disponible,
            creances_clients_ouvertes=sum((l.montant for l in lignes_clients), start=Decimal("0")),
            dettes_fournisseurs_ouvertes=sum((l.montant for l in lignes_fournisseurs), start=Decimal("0")),
            echeances_clients_en_retard=sum(
                1 for l in lignes_clients if l.jours_retard is not None and l.jours_retard > 0
            ),
            echeances_fournisseurs_en_retard=sum(
                1 for l in lignes_fournisseurs if l.jours_retard is not None and l.jours_retard > 0
            ),
            resultat_net_exercice=resultat_net_exercice,
        )

    def prevision_tresorerie(
        self, *, horizon_jours: int = 90, aujourd_hui: date | None = None
    ) -> PrevisionTresorerie:
        """Cahier, section 12 "Prévision de trésorerie". `horizon_jours`
        borne la fenêtre de projection (défaut 90 jours) — une échéance
        au-delà n'est pas incluse du tout (ni dans la courbe, ni dans les
        montants "sans échéance", qui ne concernent que les échéances
        sans DATE connue, pas celles hors horizon)."""
        if horizon_jours <= 0:
            raise ValidationMetier("L'horizon de prévision doit être strictement positif.")

        aujourd_hui = aujourd_hui or date.today()
        date_limite = aujourd_hui + timedelta(days=horizon_jours)
        exercice = self._exercice_courant(aujourd_hui)
        solde_actuel = self._tresorerie_disponible(exercice)

        lignes_clients = self.echeancier("client", aujourd_hui=aujourd_hui)
        lignes_fournisseurs = self.echeancier("fournisseur", aujourd_hui=aujourd_hui)

        mouvements: list[tuple[date, str, Decimal]] = []
        montant_sans_echeance_clients = Decimal("0")
        for ligne in lignes_clients:
            if ligne.date_echeance is None:
                montant_sans_echeance_clients += ligne.montant
            elif aujourd_hui <= ligne.date_echeance <= date_limite:
                mouvements.append((ligne.date_echeance, f"Encaissement — {ligne.raison_sociale_tiers}", ligne.montant))

        montant_sans_echeance_fournisseurs = Decimal("0")
        for ligne in lignes_fournisseurs:
            if ligne.date_echeance is None:
                montant_sans_echeance_fournisseurs += ligne.montant
            elif aujourd_hui <= ligne.date_echeance <= date_limite:
                # `montant` est déjà positif (dû à ce fournisseur, voir
                # `echeancier`) : un décaissement diminue la trésorerie,
                # donc signe négatif ici.
                mouvements.append((ligne.date_echeance, f"Décaissement — {ligne.raison_sociale_tiers}", -ligne.montant))

        mouvements.sort(key=lambda m: m[0])

        lignes_prevision: list[LignePrevisionTresorerie] = []
        solde_cumule = solde_actuel
        for date_echeance, libelle, montant in mouvements:
            solde_cumule += montant
            lignes_prevision.append(
                LignePrevisionTresorerie(
                    date_echeance=date_echeance,
                    libelle=libelle,
                    montant=montant,
                    solde_cumule=solde_cumule,
                )
            )

        return PrevisionTresorerie(
            solde_actuel=solde_actuel,
            horizon_jours=horizon_jours,
            lignes=lignes_prevision,
            solde_final_projete=solde_cumule,
            montant_sans_echeance_clients=montant_sans_echeance_clients,
            montant_sans_echeance_fournisseurs=montant_sans_echeance_fournisseurs,
        )

    def tableau_comptabilite(self, *, aujourd_hui: date | None = None) -> TableauComptabilite:
        aujourd_hui = aujourd_hui or date.today()
        seuil_cloture = aujourd_hui + timedelta(days=JOURS_CLOTURE_PROCHE)
        return TableauComptabilite(
            ecritures_brouillon=self.reporting.compter_ecritures_brouillon(),
            lignes_bancaires_non_lettrees=self.reporting.compter_lignes_bancaires_non_lettrees(),
            clotures_a_venir=self.reporting.compter_exercices_ouverts_avant(seuil_cloture),
            demandes_non_traitees=self.reporting.compter_demandes_non_traitees(),
        )

    def _exercice_courant(self, aujourd_hui: date) -> Exercice | None:
        """L'exercice couvrant aujourd'hui s'il existe ; à défaut, le plus
        récent des exercices encore ouverts (par date de début) — ce
        deuxième cas couvre un exercice en retard de clôture, dont la date
        de fin est déjà dépassée (voir aussi `notifications/alertes.py`,
        qui détecte justement cette situation)."""
        exercice = self.exercices.obtenir_pour_date(aujourd_hui)
        if exercice is not None:
            return exercice
        ouverts = self.exercices.lister_ouverts()
        if not ouverts:
            return None
        return max(ouverts, key=lambda e: e.date_debut)

    @staticmethod
    def _colonne_compte_collectif(type_tiers: str):
        if type_tiers == "client":
            return Tiers.compte_collectif_client_id
        if type_tiers == "fournisseur":
            return Tiers.compte_collectif_fournisseur_id
        raise ValidationMetier("type_tiers doit valoir 'client' ou 'fournisseur'.")

    def _obtenir_exercice_ou_lever(self, exercice_id: uuid.UUID) -> Exercice:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        return exercice