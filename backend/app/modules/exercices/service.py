"""Règles métier du module exercices.

Contrairement à `ServiceDroits`, `ServiceUtilisateurs` et
`ServiceEntreprises` (services globaux, construits avec `db` seul),
`ServiceExercices` est le premier service cloisonné par entreprise : il
prend `entreprise_id` à la construction, comme les repositories dont il
dépend. C'est le routeur qui le construira à partir du `ContexteEntreprise`
résolu par `api/deps.py` :

    service = ServiceExercices(db, contexte.entreprise_id)

Les contrôles de fond sur les écritures elles-mêmes (section 8.5 :
"période clôturée", "exercice clôturé") viendront avec le module
`comptabilite` ; ce service ne porte que le cycle de vie de l'exercice et
de ses périodes.
"""

import calendar
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import RessourceIntrouvable, ValidationMetier
from app.modules.exercices.models import Exercice, Periode, StatutExercice, StatutPeriode
from app.modules.exercices.repository import RepositoryExercice, RepositoryPeriode
from app.modules.journal_activite.models import TypeAction
from app.modules.journal_activite.service import ServiceJournalActivite


MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


class ServiceExercices:
    def __init__(self, db: Session, entreprise_id: uuid.UUID) -> None:
        self.db = db
        self.entreprise_id = entreprise_id
        self.exercices = RepositoryExercice(db, entreprise_id)
        self.periodes = RepositoryPeriode(db, entreprise_id)
        self.journal = ServiceJournalActivite(db)

    # --- Exercices ----------------------------------------------------

    def creer_exercice(
        self,
        *,
        auteur_id: uuid.UUID,
        date_debut: date,
        date_fin: date,
        exercice_precedent_id: uuid.UUID | None = None,
    ) -> Exercice:
        if date_fin <= date_debut:
            raise ValidationMetier("La date de fin doit être postérieure à la date de début.")

        chevauchements = self.exercices.chevauche(date_debut, date_fin)
        if chevauchements:
            raise ValidationMetier(
                "Cet exercice chevauche un exercice existant.",
                details={"exercice_en_conflit": str(chevauchements[0].id)},
            )

        if exercice_precedent_id is not None:
            # `obtenir` est filtré par entreprise : lève naturellement une
            # incohérence si l'exercice précédent appartient à une autre
            # entreprise, en le traitant comme introuvable.
            precedent = self.exercices.obtenir(exercice_precedent_id)
            if precedent is None:
                raise RessourceIntrouvable("Exercice précédent introuvable.")

        exercice = Exercice(
            date_debut=date_debut,
            date_fin=date_fin,
            statut=StatutExercice.OUVERT.value,
            exercice_precedent_id=exercice_precedent_id,
        )
        self.exercices.ajouter(exercice)
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Exercice",
            objet_id=exercice.id,
            description=f"Création de l'exercice {date_debut} → {date_fin}.",
            valeurs_apres={"date_debut": str(date_debut), "date_fin": str(date_fin)},
        )
        return exercice

    def cloturer_exercice(self, exercice_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        if exercice.statut == StatutExercice.CLOTURE.value:
            raise ValidationMetier("Cet exercice est déjà clôturé.")

        periodes_ouvertes = [
            p
            for p in self.periodes.lister_pour_exercice(exercice_id)
            if p.statut == StatutPeriode.OUVERTE.value
        ]
        if periodes_ouvertes:
            raise ValidationMetier(
                "Toutes les périodes doivent être clôturées avant l'exercice.",
                details={"periodes_ouvertes": [str(p.id) for p in periodes_ouvertes]},
            )

        exercice.statut = StatutExercice.CLOTURE.value
        self.db.flush()
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Exercice",
            objet_id=exercice.id,
            description="Clôture de l'exercice.",
            valeurs_avant={"statut": StatutExercice.OUVERT.value},
            valeurs_apres={"statut": StatutExercice.CLOTURE.value},
        )

    def reouvrir_exercice(self, exercice_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        """Le contrôle des droits autorisant cette action (cahier, section
        7.2) est fait au niveau du router, pas ici."""
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        if exercice.statut == StatutExercice.OUVERT.value:
            raise ValidationMetier("Cet exercice est déjà ouvert.")
        exercice.statut = StatutExercice.OUVERT.value
        self.db.flush()
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Exercice",
            objet_id=exercice.id,
            description="Réouverture de l'exercice.",
            valeurs_avant={"statut": StatutExercice.CLOTURE.value},
            valeurs_apres={"statut": StatutExercice.OUVERT.value},
        )

    def obtenir_exercice(self, exercice_id: uuid.UUID) -> Exercice:
        return self._obtenir_exercice_ou_lever(exercice_id)

    def lister_exercices(self) -> list[Exercice]:
        return self.exercices.lister()

    # --- Périodes -------------------------------------------------------

    def creer_periode(
        self,
        *,
        auteur_id: uuid.UUID,
        exercice_id: uuid.UUID,
        date_debut: date,
        date_fin: date,
        libelle: str | None = None,
    ) -> Periode:
        exercice = self._obtenir_exercice_ou_lever(exercice_id)

        if date_fin <= date_debut:
            raise ValidationMetier("La date de fin doit être postérieure à la date de début.")
        if date_debut < exercice.date_debut or date_fin > exercice.date_fin:
            raise ValidationMetier("La période doit rester à l'intérieur de l'exercice.")

        chevauchements = self.periodes.chevauche(exercice_id, date_debut, date_fin)
        if chevauchements:
            raise ValidationMetier(
                "Cette période chevauche une période existante de l'exercice.",
                details={"periode_en_conflit": str(chevauchements[0].id)},
            )

        periode = Periode(
            exercice_id=exercice_id,
            libelle=libelle,
            date_debut=date_debut,
            date_fin=date_fin,
            statut=StatutPeriode.OUVERTE.value,
        )
        self.periodes.ajouter(periode)
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.CREER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Periode",
            objet_id=periode.id,
            description=f"Création de la période {date_debut} → {date_fin}.",
            valeurs_apres={"date_debut": str(date_debut), "date_fin": str(date_fin)},
        )
        return periode

    def generer_periodes_mensuelles(
        self, exercice_id: uuid.UUID, *, auteur_id: uuid.UUID
    ) -> list[Periode]:
        """Crée les mois de travail manquants de l'exercice (un par mois
        civil, le premier et le dernier étant tronqués aux bornes de
        l'exercice). Idempotent : un mois qui chevauche déjà une période
        existante est sauté. Renvoie les périodes créées."""
        exercice = self._obtenir_exercice_ou_lever(exercice_id)
        creees: list[Periode] = []
        debut = exercice.date_debut
        while debut <= exercice.date_fin:
            fin_mois = date(debut.year, debut.month, calendar.monthrange(debut.year, debut.month)[1])
            fin = min(fin_mois, exercice.date_fin)
            if fin > debut and not self.periodes.chevauche(exercice_id, debut, fin):
                periode = Periode(
                    exercice_id=exercice_id,
                    libelle=f"{MOIS_FR[debut.month - 1]} {debut.year}",
                    date_debut=debut,
                    date_fin=fin,
                    statut=StatutPeriode.OUVERTE.value,
                )
                self.periodes.ajouter(periode)
                creees.append(periode)
            debut = fin + timedelta(days=1)
        if creees:
            self.journal.enregistrer(
                module="exercices",
                type_action=TypeAction.CREER,
                utilisateur_id=auteur_id,
                entreprise_id=self.entreprise_id,
                type_objet="Periode",
                description=f"Génération de {len(creees)} mois de travail pour l'exercice {exercice.date_debut} → {exercice.date_fin}.",
                valeurs_apres={"nombre": len(creees)},
            )
        return creees

    def cloturer_periode(self, periode_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        periode = self._obtenir_periode_ou_lever(periode_id)
        if periode.statut == StatutPeriode.CLOTUREE.value:
            raise ValidationMetier("Cette période est déjà clôturée.")
        periode.statut = StatutPeriode.CLOTUREE.value
        self.db.flush()
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.VALIDER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Periode",
            objet_id=periode.id,
            description="Clôture de la période.",
            valeurs_avant={"statut": StatutPeriode.OUVERTE.value},
            valeurs_apres={"statut": StatutPeriode.CLOTUREE.value},
        )

    def reouvrir_periode(self, periode_id: uuid.UUID, *, auteur_id: uuid.UUID) -> None:
        periode = self._obtenir_periode_ou_lever(periode_id)
        exercice = self._obtenir_exercice_ou_lever(periode.exercice_id)
        if exercice.statut == StatutExercice.CLOTURE.value:
            raise ValidationMetier("Impossible de rouvrir une période d'un exercice clôturé.")
        if periode.statut == StatutPeriode.OUVERTE.value:
            raise ValidationMetier("Cette période est déjà ouverte.")
        periode.statut = StatutPeriode.OUVERTE.value
        self.db.flush()
        self.journal.enregistrer(
            module="exercices",
            type_action=TypeAction.ANNULER,
            utilisateur_id=auteur_id,
            entreprise_id=self.entreprise_id,
            type_objet="Periode",
            objet_id=periode.id,
            description="Réouverture de la période.",
            valeurs_avant={"statut": StatutPeriode.CLOTUREE.value},
            valeurs_apres={"statut": StatutPeriode.OUVERTE.value},
        )

    def lister_periodes(self, exercice_id: uuid.UUID) -> list[Periode]:
        return sorted(self.periodes.lister_pour_exercice(exercice_id), key=lambda p: p.date_debut)

    # --- Aides internes ---------------------------------------------------

    def _obtenir_exercice_ou_lever(self, exercice_id: uuid.UUID) -> Exercice:
        exercice = self.exercices.obtenir(exercice_id)
        if exercice is None:
            raise RessourceIntrouvable("Exercice introuvable.")
        return exercice

    def _obtenir_periode_ou_lever(self, periode_id: uuid.UUID) -> Periode:
        periode = self.periodes.obtenir(periode_id)
        if periode is None:
            raise RessourceIntrouvable("Période introuvable.")
        return periode