"""Règles métier du module stocks.

Voir la note de tête de fichier de `models.py` pour les décisions actées
(CMUP/FIFO au choix par article, stock jamais négatif, pas de génération
d'écriture, mouvements append-only).

Calcul du coût selon la méthode de l'article :

- CMUP : `creer_mouvement_entree` recalcule `Article.cout_unitaire_moyen`
  par la formule usuelle (ancienne valeur de stock + valeur de l'entrée)
  / (ancienne quantité + quantité entrée). `creer_mouvement_sortie`
  applique ce coût moyen COURANT tel quel — une sortie ne fait jamais
  varier le coût moyen, seulement la quantité et la valeur de stock.
- FIFO : `creer_mouvement_entree` crée un `LotEntreeStock` avec son propre
  coût, sans toucher à un quelconque coût moyen. `creer_mouvement_sortie`
  consomme les lots disponibles du plus ancien au plus récent
  (`RepositoryLotsEntreeStock.lister_lots_disponibles`), jusqu'à
  satisfaire la quantité demandée ; le coût unitaire retenu pour le
  mouvement de sortie est la moyenne pondérée des lots effectivement
  consommés (peut mélanger plusieurs coûts d'entrée différents).

Dans les deux cas, si la quantité demandée en sortie dépasse
`Article.quantite_en_stock`, la sortie est rejetée avant toute
modification — jamais de stock négatif (voir la note de tête de fichier
de `models.py`).
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.models import Ecriture
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.comptabilite.service import LigneSaisie, ServiceComptabilite
from app.modules.exercices.repository import RepositoryExercice
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.stocks.models import (
    Article,
    InventairePhysique,
    LigneConsommationLot,
    LotEntreeStock,
    MethodeValorisation,
    MouvementStock,
    TypeMouvement,
)
from app.modules.stocks.repository import (
    RepositoryArticles,
    RepositoryInventairesPhysiques,
    RepositoryLignesConsommationLot,
    RepositoryLotsEntreeStock,
    RepositoryMouvementsStock,
)
from app.modules.tiers.repository import RepositoryTiers

CLASSE_COMPTE_STOCK = 3
QUANTIZE_QUANTITE = Decimal("0.001")
QUANTIZE_COUT_UNITAIRE = Decimal("0.0001")
QUANTIZE_MONTANT = Decimal("0.01")


@dataclass
class MouvementEntreeCreation:
    article_id: uuid.UUID
    date_mouvement: date
    quantite: Decimal
    cout_unitaire: Decimal
    reference: str | None = None
    libelle: str | None = None
    tiers_id: uuid.UUID | None = None


@dataclass
class MouvementSortieCreation:
    article_id: uuid.UUID
    date_mouvement: date
    quantite: Decimal
    reference: str | None = None
    libelle: str | None = None
    tiers_id: uuid.UUID | None = None


class ServiceStocks:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.articles = RepositoryArticles(db, entreprise_id)
        self.mouvements = RepositoryMouvementsStock(db, entreprise_id)
        self.lots = RepositoryLotsEntreeStock(db, entreprise_id)
        self.lignes_consommation = RepositoryLignesConsommationLot(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.inventaires = RepositoryInventairesPhysiques(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    # --- Articles ----------------------------------------------------------

    def creer_article(
        self,
        *,
        code: str,
        libelle: str,
        unite: str,
        methode_valorisation: MethodeValorisation,
        compte_stock_id: uuid.UUID,
        auteur_id: uuid.UUID,
    ) -> Article:
        if self.articles.obtenir_par_code(code) is not None:
            raise ValidationMetier(f"Le code article '{code}' est déjà utilisé.")

        compte = self.comptes.obtenir(compte_stock_id)
        if compte is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")
        if compte.classe != CLASSE_COMPTE_STOCK:
            raise ValidationMetier(
                f"Le compte {compte.numero} n'est pas un compte de stock "
                f"(classe {CLASSE_COMPTE_STOCK} attendue, classe {compte.classe} fournie)."
            )

        article = Article(
            code=code,
            libelle=libelle,
            unite=unite,
            methode_valorisation=methode_valorisation.value,
            compte_stock_id=compte_stock_id,
            actif=True,
            quantite_en_stock=Decimal("0"),
            cout_unitaire_moyen=Decimal("0"),
            valeur_stock=Decimal("0"),
        )
        self.articles.ajouter(article)
        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Article",
            objet_id=article.id,
            description=f"Création de l'article '{code}' ({libelle}).",
            valeurs_apres={"code": code, "methode_valorisation": methode_valorisation.value},
        )
        return article

    def modifier_article(
        self,
        article_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        libelle: str | None = None,
        unite: str | None = None,
    ) -> Article:
        """Mise à jour volontairement limitée aux champs descriptifs : la
        méthode de valorisation et le compte de stock ne se changent pas
        ici — les modifier en cours de vie invaliderait l'historique des
        mouvements déjà enregistrés (voir la note de tête de fichier)."""
        article = self._obtenir_article_ou_lever(article_id)

        if libelle is not None:
            article.libelle = libelle
        if unite is not None:
            article.unite = unite
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Article",
            objet_id=article.id,
            description=f"Modification de l'article '{article.code}'.",
        )
        return article

    def desactiver_article(self, article_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Article:
        article = self._obtenir_article_ou_lever(article_id)
        if not article.actif:
            raise ValidationMetier("Cet article est déjà désactivé.")

        article.actif = False
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Article",
            objet_id=article.id,
            description=f"Désactivation de l'article '{article.code}'.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )
        return article

    def reactiver_article(self, article_id: uuid.UUID, *, auteur_id: uuid.UUID) -> Article:
        article = self._obtenir_article_ou_lever(article_id)
        if article.actif:
            raise ValidationMetier("Cet article est déjà actif.")

        article.actif = True
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Article",
            objet_id=article.id,
            description=f"Réactivation de l'article '{article.code}'.",
            valeurs_avant={"actif": False},
            valeurs_apres={"actif": True},
        )
        return article

    def obtenir_article(self, article_id: uuid.UUID) -> Article:
        return self._obtenir_article_ou_lever(article_id)

    def lister_articles(self, *, actifs_seulement: bool = True) -> list[Article]:
        return self.articles.lister(actifs_seulement=actifs_seulement)

    # --- Mouvements ----------------------------------------------------------

    def creer_mouvement_entree(
        self, donnees: MouvementEntreeCreation, *, auteur_id: uuid.UUID
    ) -> MouvementStock:
        article = self._obtenir_article_ou_lever(donnees.article_id)
        if not article.actif:
            raise ValidationMetier("Impossible d'enregistrer un mouvement sur un article désactivé.")
        if donnees.quantite <= 0:
            raise ValidationMetier("La quantité doit être strictement positive.")
        if donnees.cout_unitaire < 0:
            raise ValidationMetier("Le coût unitaire ne peut pas être négatif.")
        if donnees.tiers_id is not None and self.tiers.obtenir(donnees.tiers_id) is None:
            raise RessourceIntrouvable("Tiers introuvable.")

        quantite = donnees.quantite.quantize(QUANTIZE_QUANTITE, rounding=ROUND_HALF_UP)
        cout_unitaire = donnees.cout_unitaire.quantize(QUANTIZE_COUT_UNITAIRE, rounding=ROUND_HALF_UP)
        cout_total = (quantite * cout_unitaire).quantize(QUANTIZE_MONTANT, rounding=ROUND_HALF_UP)

        mouvement = MouvementStock(
            article_id=article.id,
            type_mouvement=TypeMouvement.ENTREE.value,
            date_mouvement=donnees.date_mouvement,
            quantite=quantite,
            cout_unitaire=cout_unitaire,
            cout_total=cout_total,
            reference=donnees.reference,
            libelle=donnees.libelle,
            tiers_id=donnees.tiers_id,
        )
        self.mouvements.ajouter(mouvement)
        self.db.flush()

        if article.methode_valorisation == MethodeValorisation.FIFO.value:
            self.lots.ajouter(
                LotEntreeStock(
                    article_id=article.id,
                    mouvement_entree_id=mouvement.id,
                    date_entree=donnees.date_mouvement,
                    quantite_initiale=quantite,
                    quantite_restante=quantite,
                    cout_unitaire=cout_unitaire,
                )
            )
        else:
            # CMUP : nouvelle moyenne = (ancienne valeur + valeur entrée) / (ancienne quantité + quantité entrée).
            nouvelle_quantite = article.quantite_en_stock + quantite
            nouvelle_valeur = article.valeur_stock + cout_total
            article.cout_unitaire_moyen = (nouvelle_valeur / nouvelle_quantite).quantize(
                QUANTIZE_COUT_UNITAIRE, rounding=ROUND_HALF_UP
            )

        article.quantite_en_stock += quantite
        article.valeur_stock += cout_total
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="MouvementStock",
            objet_id=mouvement.id,
            description=f"Entrée de {quantite} {article.unite} sur '{article.code}'.",
            valeurs_apres={"quantite": str(quantite), "cout_total": str(cout_total)},
        )
        return mouvement

    def creer_mouvement_sortie(
        self, donnees: MouvementSortieCreation, *, auteur_id: uuid.UUID
    ) -> MouvementStock:
        article = self._obtenir_article_ou_lever(donnees.article_id)
        if not article.actif:
            raise ValidationMetier("Impossible d'enregistrer un mouvement sur un article désactivé.")
        if donnees.quantite <= 0:
            raise ValidationMetier("La quantité doit être strictement positive.")
        if donnees.tiers_id is not None and self.tiers.obtenir(donnees.tiers_id) is None:
            raise RessourceIntrouvable("Tiers introuvable.")

        quantite = donnees.quantite.quantize(QUANTIZE_QUANTITE, rounding=ROUND_HALF_UP)
        if quantite > article.quantite_en_stock:
            raise ValidationMetier(
                f"Stock insuffisant sur '{article.code}' : {article.quantite_en_stock} "
                f"{article.unite} disponible(s), {quantite} demandé(s)."
            )

        mouvement = MouvementStock(
            article_id=article.id,
            type_mouvement=TypeMouvement.SORTIE.value,
            date_mouvement=donnees.date_mouvement,
            quantite=quantite,
            cout_unitaire=Decimal("0"),  # renseigné ci-dessous selon la méthode
            cout_total=Decimal("0"),
            reference=donnees.reference,
            libelle=donnees.libelle,
            tiers_id=donnees.tiers_id,
        )
        self.mouvements.ajouter(mouvement)
        self.db.flush()

        if article.methode_valorisation == MethodeValorisation.FIFO.value:
            cout_total = self._consommer_fifo(article, mouvement, quantite)
        else:
            cout_total = (quantite * article.cout_unitaire_moyen).quantize(
                QUANTIZE_MONTANT, rounding=ROUND_HALF_UP
            )

        cout_unitaire = (
            (cout_total / quantite).quantize(QUANTIZE_COUT_UNITAIRE, rounding=ROUND_HALF_UP)
            if quantite > 0
            else Decimal("0")
        )
        mouvement.cout_unitaire = cout_unitaire
        mouvement.cout_total = cout_total

        article.quantite_en_stock -= quantite
        article.valeur_stock -= cout_total
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="MouvementStock",
            objet_id=mouvement.id,
            description=f"Sortie de {quantite} {article.unite} sur '{article.code}'.",
            valeurs_apres={"quantite": str(quantite), "cout_total": str(cout_total)},
        )
        return mouvement

    def obtenir_mouvement(self, mouvement_id: uuid.UUID) -> MouvementStock:
        mouvement = self.mouvements.obtenir(mouvement_id)
        if mouvement is None:
            raise RessourceIntrouvable("Mouvement de stock introuvable.")
        return mouvement

    def lister_mouvements(
        self, *, article_id: uuid.UUID | None = None, type_mouvement: str | None = None
    ) -> list[MouvementStock]:
        return self.mouvements.lister(article_id=article_id, type_mouvement=type_mouvement)

    def lister_lignes_consommation(self, mouvement_id: uuid.UUID) -> list[LigneConsommationLot]:
        return self.lignes_consommation.lister_pour_mouvement(mouvement_id)

    def generer_ecriture_mouvement(
        self,
        mouvement_id: uuid.UUID,
        *,
        journal_id: uuid.UUID,
        compte_contrepartie_id: uuid.UUID,
        auteur_id: uuid.UUID,
    ) -> Ecriture:
        """Comptabilise un mouvement de stock : une entrée débite le
        compte de stock de l'article et crédite `compte_contrepartie_id`
        (typiquement un compte d'achat ou de fournisseur) ; une sortie
        fait l'inverse (typiquement un compte de vente ou de client, ou de
        variation de stock). `compte_contrepartie_id` n'est pas stocké sur
        le mouvement — il dépend du contexte (achat, vente, régularisation...)
        et est fourni à l'appel, voir la note de tête de fichier de
        `models.py`.

        `MouvementStock` n'a pas d'`exercice_id` propre (à la différence
        de `LigneAmortissement`/`BulletinPaie`) : l'exercice se retrouve
        par la date du mouvement (`RepositoryExercice.obtenir_pour_date`)."""
        mouvement = self.obtenir_mouvement(mouvement_id)
        if mouvement.ecriture_id is not None:
            raise ValidationMetier("Ce mouvement a déjà une écriture générée.")

        article = self._obtenir_article_ou_lever(mouvement.article_id)
        if self.comptes.obtenir(compte_contrepartie_id) is None:
            raise RessourceIntrouvable("Compte comptable introuvable.")

        exercice = self.exercices.obtenir_pour_date(mouvement.date_mouvement)
        if exercice is None:
            raise ValidationMetier(
                f"Aucun exercice ne couvre la date du mouvement ({mouvement.date_mouvement})."
            )

        if mouvement.type_mouvement == TypeMouvement.ENTREE.value:
            lignes_saisies = [
                LigneSaisie(compte_id=article.compte_stock_id, debit=mouvement.cout_total),
                LigneSaisie(compte_id=compte_contrepartie_id, credit=mouvement.cout_total),
            ]
            libelle_type = "Entrée"
        else:
            lignes_saisies = [
                LigneSaisie(compte_id=compte_contrepartie_id, debit=mouvement.cout_total),
                LigneSaisie(compte_id=article.compte_stock_id, credit=mouvement.cout_total),
            ]
            libelle_type = "Sortie"

        service_comptabilite = ServiceComptabilite(self.db, self.entreprise_id)
        ecriture = service_comptabilite.creer_ecriture(
            auteur_id=auteur_id,
            journal_id=journal_id,
            exercice_id=exercice.id,
            date_ecriture=mouvement.date_mouvement,
            libelle=f"{libelle_type} de stock - {article.code} ({article.libelle})",
            lignes=lignes_saisies,
        )

        mouvement.ecriture_id = ecriture.id
        self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="MouvementStock",
            objet_id=mouvement.id,
            description=f"Génération de l'écriture pour le mouvement sur '{article.code}'.",
            valeurs_apres={"ecriture_id": str(ecriture.id)},
        )
        return ecriture

    # --- Inventaires physiques ------------------------------------------------

    def creer_inventaire_physique(
        self,
        *,
        article_id: uuid.UUID,
        exercice_id: uuid.UUID,
        date_inventaire: date,
        quantite_physique: Decimal,
        journal_id: uuid.UUID | None,
        compte_contrepartie_id: uuid.UUID | None,
        auteur_id: uuid.UUID,
    ) -> InventairePhysique:
        """Constate l'écart entre le stock théorique (tenu par les
        mouvements) et un comptage physique, et le corrige si besoin —
        voir la note de tête de fichier de `models.py`.

        `quantite_theorique` est un instantané de `article.quantite_en_stock`
        à l'instant du comptage : un inventaire physique ne recalcule rien
        rétroactivement, il constate l'écart tel qu'il se présente ce
        jour-là.

        Si l'écart est nul, aucun mouvement n'est créé (`journal_id`/
        `compte_contrepartie_id` peuvent être omis). Sinon :
        - surplus (écart > 0) → un mouvement d'ENTRÉE de `ecart` unités, au
          coût unitaire moyen courant de l'article (`valeur_stock` /
          `quantite_en_stock`) pour ne pas fausser le CMUP par une
          valorisation arbitraire ;
        - manquant (écart < 0) → un mouvement de SORTIE de `abs(ecart)`
          unités — le coût est calculé par `creer_mouvement_sortie` selon
          la méthode de l'article, exactement comme une sortie normale.

        Dans les deux cas, l'écriture est générée dans la foulée via
        `generer_ecriture_mouvement`, avec le compte de contrepartie fourni
        par l'appelant (typiquement un compte de charge classe 6 pour un
        manquant — perte sur stock —, ou de produit classe 7 pour un
        surplus) : ce module ne distingue pas marchandises achetées
        (variation classe 6) de produits fabriqués (variation classe 7), le
        choix du bon compte reste à l'utilisateur, comme pour toute
        génération d'écriture de mouvement (voir la note de
        `generer_ecriture_mouvement`)."""
        article = self._obtenir_article_ou_lever(article_id)
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        if exercice.statut != StatutExercice.OUVERT.value:
            raise ValidationMetier("Impossible d'enregistrer un inventaire sur un exercice clôturé.")

        quantite_physique = quantite_physique.quantize(QUANTIZE_QUANTITE, rounding=ROUND_HALF_UP)
        quantite_theorique = article.quantite_en_stock
        ecart = (quantite_physique - quantite_theorique).quantize(QUANTIZE_QUANTITE, rounding=ROUND_HALF_UP)

        inventaire = InventairePhysique(
            article_id=article.id,
            exercice_id=exercice_id,
            date_inventaire=date_inventaire,
            quantite_theorique=quantite_theorique,
            quantite_physique=quantite_physique,
            ecart=ecart,
        )
        self.inventaires.ajouter(inventaire)
        self.db.flush()

        mouvement: MouvementStock | None = None
        if ecart != 0:
            if journal_id is None or compte_contrepartie_id is None:
                raise ValidationMetier(
                    "Un journal et un compte de contrepartie sont requis dès lors que "
                    "l'inventaire fait apparaître un écart."
                )
            if ecart > 0:
                cout_unitaire_ajustement = (
                    (article.valeur_stock / article.quantite_en_stock).quantize(
                        QUANTIZE_COUT_UNITAIRE, rounding=ROUND_HALF_UP
                    )
                    if article.quantite_en_stock > 0
                    else Decimal("0")
                )
                mouvement = self.creer_mouvement_entree(
                    MouvementEntreeCreation(
                        article_id=article.id,
                        date_mouvement=date_inventaire,
                        quantite=ecart,
                        cout_unitaire=cout_unitaire_ajustement,
                        libelle=f"Ajustement d'inventaire (surplus) - {article.code}",
                    ),
                    auteur_id=auteur_id,
                )
            else:
                mouvement = self.creer_mouvement_sortie(
                    MouvementSortieCreation(
                        article_id=article.id,
                        date_mouvement=date_inventaire,
                        quantite=abs(ecart),
                        libelle=f"Ajustement d'inventaire (manquant) - {article.code}",
                    ),
                    auteur_id=auteur_id,
                )
            self.generer_ecriture_mouvement(
                mouvement.id,
                journal_id=journal_id,
                compte_contrepartie_id=compte_contrepartie_id,
                auteur_id=auteur_id,
            )
            inventaire.mouvement_ajustement_id = mouvement.id
            self.db.flush()

        self.journal_activite.enregistrer(
            module="stocks",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="InventairePhysique",
            objet_id=inventaire.id,
            description=(
                f"Inventaire physique de '{article.code}' : théorique {quantite_theorique}, "
                f"physique {quantite_physique}, écart {ecart}."
            ),
            valeurs_apres={"ecart": str(ecart)},
        )
        return inventaire

    def obtenir_inventaire_physique(self, inventaire_id: uuid.UUID) -> InventairePhysique:
        inventaire = self.inventaires.obtenir(inventaire_id)
        if inventaire is None:
            raise RessourceIntrouvable("Inventaire physique introuvable.")
        return inventaire

    def lister_inventaires_physiques(
        self, *, article_id: uuid.UUID | None = None, exercice_id: uuid.UUID | None = None
    ) -> list[InventairePhysique]:
        return self.inventaires.lister(article_id=article_id, exercice_id=exercice_id)
    # --- Aides internes ------------------------------------------------------

    def _consommer_fifo(
        self, article: Article, mouvement_sortie: MouvementStock, quantite: Decimal
    ) -> Decimal:
        """Consomme les lots disponibles du plus ancien au plus récent
        jusqu'à satisfaire `quantite`, trace chaque prélèvement dans
        `LigneConsommationLot`, et retourne le coût total de la sortie.

        Le contrôle `quantite <= article.quantite_en_stock` (fait par
        l'appelant) garantit que les lots disponibles suffisent : l'état
        dénormalisé de l'article est maintenu en cohérence avec la somme
        des reliquats de lots à chaque mouvement, donc si la quantité
        globale est suffisante, les lots le sont aussi."""
        lots_disponibles = self.lots.lister_lots_disponibles(article.id)
        restant_a_consommer = quantite
        cout_total = Decimal("0")

        for lot in lots_disponibles:
            if restant_a_consommer <= 0:
                break
            quantite_prise = min(lot.quantite_restante, restant_a_consommer)
            lot.quantite_restante -= quantite_prise
            cout_ligne = (quantite_prise * lot.cout_unitaire).quantize(
                QUANTIZE_MONTANT, rounding=ROUND_HALF_UP
            )
            cout_total += cout_ligne
            self.lignes_consommation.ajouter(
                LigneConsommationLot(
                    mouvement_sortie_id=mouvement_sortie.id,
                    lot_id=lot.id,
                    quantite_consommee=quantite_prise,
                    cout_unitaire=lot.cout_unitaire,
                )
            )
            restant_a_consommer -= quantite_prise

        if restant_a_consommer > 0:
            # Ne devrait jamais arriver si `quantite_en_stock` est resté
            # cohérent avec la somme des lots (voir la docstring) — filet
            # de sécurité plutôt qu'un cas attendu.
            raise ValidationMetier(
                f"Lots FIFO insuffisants pour satisfaire la sortie demandée sur '{article.code}'."
            )

        self.db.flush()
        return cout_total.quantize(QUANTIZE_MONTANT, rounding=ROUND_HALF_UP)

    def _obtenir_article_ou_lever(self, article_id: uuid.UUID) -> Article:
        article = self.articles.obtenir(article_id)
        if article is None:
            raise RessourceIntrouvable("Article introuvable.")
        return article