"""Règles métier du module tiers.

Construit avec `(db, entreprise_id)`, comme `ServiceExercices` et
`ServiceComptabilite`. Dépend de `RepositoryComptes` (module `comptabilite`)
pour vérifier qu'un compte collectif référencé existe bien, est éligible
(`est_collectif`) et actif — cette vérification traverse les modules mais
reste dans le bon sens (`tiers` dépend de `comptabilite`, jamais l'inverse).

`creer_tiers` ne bloque JAMAIS sur un NIF déjà vu : un même NIF peut
légitimement correspondre à plusieurs établissements d'une même société.
Il avertit (`Conflit`, avec le détail des tiers existants) et laisse
l'appelant confirmer explicitement (`confirmer_malgre_doublon=True`) pour
créer quand même — ce n'est pas une règle d'intégrité, c'est une aide à la
saisie.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import Conflit, RessourceIntrouvable, ValidationMetier
from app.modules.comptabilite.repository import RepositoryComptes
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite
from app.modules.tiers.models import Tiers
from app.modules.tiers.repository import RepositoryTiers


class ServiceTiers:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.tiers = RepositoryTiers(db, entreprise_id)
        self.comptes = RepositoryComptes(db, entreprise_id)
        self.journal_activite = ServiceJournalActivite(db)

    def creer_tiers(
        self,
        *,
        auteur_id: uuid.UUID,
        code: str,
        raison_sociale: str,
        nif: str | None = None,
        rccm: str | None = None,
        adresse: str | None = None,
        email: str | None = None,
        telephone: str | None = None,
        delai_paiement_jours: int | None = None,
        plafond_credit: Decimal | None = None,
        compte_collectif_client_id: uuid.UUID | None = None,
        compte_collectif_fournisseur_id: uuid.UUID | None = None,
        confirmer_malgre_doublon: bool = False,
    ) -> Tiers:
        if compte_collectif_client_id is None and compte_collectif_fournisseur_id is None:
            raise ValidationMetier("Un tiers doit être client, fournisseur, ou les deux.")

        if self.tiers.obtenir_par_code(code) is not None:
            raise Conflit(f"Le tiers {code} existe déjà pour cette entreprise.")

        if compte_collectif_client_id is not None:
            self._valider_compte_collectif(compte_collectif_client_id, "client")
        if compte_collectif_fournisseur_id is not None:
            self._valider_compte_collectif(compte_collectif_fournisseur_id, "fournisseur")

        if nif and not confirmer_malgre_doublon:
            doublons = self.tiers.rechercher_par_nif(nif)
            if doublons:
                raise Conflit(
                    "Un ou plusieurs tiers existants partagent ce NIF. "
                    "Confirmez (`confirmer_malgre_doublon`) pour créer quand même.",
                    details={
                        "tiers_existants": [
                            {"id": str(t.id), "code": t.code, "raison_sociale": t.raison_sociale}
                            for t in doublons
                        ]
                    },
                )

        nouveau_tiers = Tiers(
            code=code,
            raison_sociale=raison_sociale,
            nif=nif,
            rccm=rccm,
            adresse=adresse,
            email=email,
            telephone=telephone,
            delai_paiement_jours=delai_paiement_jours,
            plafond_credit=plafond_credit,
            compte_collectif_client_id=compte_collectif_client_id,
            compte_collectif_fournisseur_id=compte_collectif_fournisseur_id,
        )
        self.tiers.ajouter(nouveau_tiers)
        self.journal_activite.enregistrer(
            module="tiers",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Tiers",
            objet_id=nouveau_tiers.id,
            description=f"Création du tiers {code} — {raison_sociale}.",
            valeurs_apres={"code": code, "raison_sociale": raison_sociale},
        )
        return nouveau_tiers

    def modifier_tiers(
        self,
        tiers_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        raison_sociale: str | None = None,
        nif: str | None = None,
        rccm: str | None = None,
        adresse: str | None = None,
        email: str | None = None,
        telephone: str | None = None,
        delai_paiement_jours: int | None = None,
        plafond_credit: Decimal | None = None,
    ) -> Tiers:
        """Ne touche jamais `code` (identifiant stable une fois attribué) ni
        les comptes collectifs (voir `modifier_comptes_collectifs`, qui
        porte sa propre validation)."""
        tiers = self._obtenir_ou_lever(tiers_id)
        if raison_sociale is not None:
            tiers.raison_sociale = raison_sociale
        if nif is not None:
            tiers.nif = nif
        if rccm is not None:
            tiers.rccm = rccm
        if adresse is not None:
            tiers.adresse = adresse
        if email is not None:
            tiers.email = email
        if telephone is not None:
            tiers.telephone = telephone
        if delai_paiement_jours is not None:
            tiers.delai_paiement_jours = delai_paiement_jours
        if plafond_credit is not None:
            tiers.plafond_credit = plafond_credit
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tiers",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Tiers",
            objet_id=tiers.id,
            description=f"Modification du tiers {tiers.code}.",
        )
        return tiers

    def modifier_comptes_collectifs(
        self,
        tiers_id: uuid.UUID,
        *,
        auteur_id: uuid.UUID,
        compte_collectif_client_id: uuid.UUID | None,
        compte_collectif_fournisseur_id: uuid.UUID | None,
    ) -> Tiers:
        """Les deux valeurs sont remplacées ensemble (pas de mise à jour
        partielle) : `None` retire explicitement le rôle correspondant, ce
        qui évite l'ambiguïté d'un appel qui "oublierait" un paramètre."""
        if compte_collectif_client_id is None and compte_collectif_fournisseur_id is None:
            raise ValidationMetier("Un tiers doit être client, fournisseur, ou les deux.")

        tiers = self._obtenir_ou_lever(tiers_id)
        if compte_collectif_client_id is not None:
            self._valider_compte_collectif(compte_collectif_client_id, "client")
        if compte_collectif_fournisseur_id is not None:
            self._valider_compte_collectif(compte_collectif_fournisseur_id, "fournisseur")

        tiers.compte_collectif_client_id = compte_collectif_client_id
        tiers.compte_collectif_fournisseur_id = compte_collectif_fournisseur_id
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tiers",
            type_action=TypeAction.MODIFIER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Tiers",
            objet_id=tiers.id,
            description=f"Modification des comptes collectifs du tiers {tiers.code}.",
        )
        return tiers

    def desactiver_tiers(self, tiers_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        tiers = self._obtenir_ou_lever(tiers_id)
        if not tiers.actif:
            raise ValidationMetier("Ce tiers est déjà désactivé.")
        tiers.actif = False
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tiers",
            type_action=TypeAction.ARCHIVER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Tiers",
            objet_id=tiers.id,
            description=f"Désactivation du tiers {tiers.code}.",
            valeurs_avant={"actif": True},
            valeurs_apres={"actif": False},
        )

    def reactiver_tiers(self, tiers_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        tiers = self._obtenir_ou_lever(tiers_id)
        if tiers.actif:
            raise ValidationMetier("Ce tiers est déjà actif.")
        tiers.actif = True
        self.db.flush()
        self.journal_activite.enregistrer(
            module="tiers",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Tiers",
            objet_id=tiers.id,
            description=f"Réactivation du tiers {tiers.code}.",
            valeurs_avant={"actif": False},
            valeurs_apres={"actif": True},
        )

    def obtenir_tiers(self, tiers_id: uuid.UUID) -> Tiers:
        return self._obtenir_ou_lever(tiers_id)

    def lister_tiers(
        self,
        *,
        actifs_seulement: bool = True,
        client_seulement: bool = False,
        fournisseur_seulement: bool = False,
    ) -> list[Tiers]:
        return self.tiers.lister(
            actifs_seulement=actifs_seulement,
            client_seulement=client_seulement,
            fournisseur_seulement=fournisseur_seulement,
        )

    # --- Aides internes ---------------------------------------------------

    def _obtenir_ou_lever(self, tiers_id: uuid.UUID) -> Tiers:
        tiers = self.tiers.obtenir(tiers_id)
        if tiers is None:
            raise RessourceIntrouvable("Tiers introuvable.")
        return tiers

    def _valider_compte_collectif(self, compte_id: uuid.UUID, role: str) -> None:
        """Le compte de regroupement d'un tiers est un compte général de la
        classe 4 : 41x pour un client (ex. 411), 40x pour un fournisseur
        (ex. 401). Un compte de cette famille qui n'est pas encore marqué
        « collectif » (cas d'un plan comptable importé sans ce drapeau) le
        devient ici — un collectif est par nature lettrable, voir la
        contrainte de `comptabilite/models.py`."""
        compte = self.comptes.obtenir(compte_id)
        if compte is None:
            raise RessourceIntrouvable("Compte collectif introuvable.")
        prefixe, nature = ("41", "client (41x, ex. 411)") if role == "client" else ("40", "fournisseur (40x, ex. 401)")
        if not compte.numero.startswith(prefixe):
            raise ValidationMetier(
                f"Le compte {compte.numero} ne peut pas servir de compte {nature} : "
                f"choisissez un compte de regroupement {prefixe}x."
            )
        if not compte.actif:
            raise ValidationMetier(f"Le compte {compte.numero} est désactivé.")
        if not compte.est_collectif:
            compte.est_collectif = True
            compte.lettrable = True
            self.db.flush()