"""Routes HTTP du module comptabilite.

Deux niveaux pour la partie référentiel, comme dans `service.py` :

- `/comptabilite/comptes` : administration du référentiel global,
  réservée à l'administrateur plateforme (`exiger_administrateur_plateforme`),
  sur le modèle de `/droits/roles`.
- `/comptabilite/entreprises/{entreprise_id}/...` : le plan comptable
  applicable, les journaux et les écritures d'une entreprise précise,
  protégés par les permissions `compte.*` / `journal.*` / `ecriture.*`
  (`exiger_permission`), sur le modèle de
  `/droits/entreprises/{entreprise_id}/affectations`.

Convention de permission : `<ressource>.<action>`, avec `archiver` pour
la désactivation, `valider` pour la validation d'une écriture et
`annuler` pour son extourne (cahier, section 6).
"""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import (
    ContexteEntreprise,
    exiger_administrateur_plateforme,
    exiger_permission,
    get_utilisateur_courant,
)
from app.core.database import get_db
from app.modules.comptabilite.schemas import (
    AppliquerModeleDonnees,
    CompteCreation,
    CompteImportResultat,
    CompteLecture,
    DelettrageDemande,
    EcritureAvecLignes,
    EcritureCreation,
    EcritureDuplication,
    EcritureExtourne,
    EcritureImportResultat,
    EcritureLecture,
    EcritureMiseAJour,
    EcritureRecurrenteAvecLignes,
    EcritureRecurrenteCreation,
    EcritureRecurrenteLecture,
    EcritureRecurrenteMiseAJour,
    EcheanceIgnoreeLecture,
    GenerationEcheancesDemande,
    GenerationEcheancesResultat,
    JournalCreation,
    JournalLecture,
    LettrageDemande,
    LettrageReponse,
    LigneLettrageLecture,
    ModeleEcritureAvecLignes,
    ModeleEcritureCreation,
    ModeleEcritureLecture,
    ModeleEcritureMiseAJour,
)
from app.modules.comptabilite.service import (
    LigneEcritureRecurrenteSaisie,
    LigneModeleSaisie,
    LigneSaisie,
    MontantLigneModele,
    ServiceComptabilite,
    ServicePlanComptableGlobal,
)
from app.modules.utilisateurs.models import Utilisateur

router = APIRouter(prefix="/comptabilite", tags=["Comptabilité"])


# --- Référentiel global : administration de plateforme -----------------------


@router.post("/comptes", response_model=CompteLecture, status_code=status.HTTP_201_CREATED)
def creer_compte_global(
    donnees: CompteCreation,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> CompteLecture:
    service = ServicePlanComptableGlobal(db)
    compte = service.creer_compte(
        auteur_id=administrateur.id,
        numero=donnees.numero,
        libelle=donnees.libelle,
        classe=donnees.classe,
        lettrable=donnees.lettrable,
        est_collectif=donnees.est_collectif,
        compte_parent_id=donnees.compte_parent_id,
    )
    db.commit()
    return CompteLecture.model_validate(compte)


@router.get("/comptes", response_model=list[CompteLecture])
def lister_comptes_globaux(
    actifs_seulement: bool = True,
    recherche: str | None = None,
    classe: int | None = None,
    limite: int = 1000,
    decalage: int = 0,
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
    db: Session = Depends(get_db),
) -> list[CompteLecture]:
    """Lecture ouverte à tout utilisateur authentifié (pas seulement à
    l'administrateur plateforme) : consulter le référentiel global ne
    dévoile aucune donnée propre à une entreprise. La création et la
    désactivation, elles, restent réservées à l'administrateur."""
    service = ServicePlanComptableGlobal(db)
    comptes = service.lister_comptes(
        actifs_seulement=actifs_seulement,
        recherche=recherche,
        classe=classe,
        limite=limite,
        decalage=decalage,
    )
    return [CompteLecture.model_validate(c) for c in comptes]


@router.post("/comptes/{compte_id}/desactiver", status_code=status.HTTP_204_NO_CONTENT)
def desactiver_compte_global(
    compte_id: uuid.UUID,
    administrateur: Utilisateur = Depends(exiger_administrateur_plateforme),
    db: Session = Depends(get_db),
) -> None:
    service = ServicePlanComptableGlobal(db)
    service.desactiver_compte(compte_id, auteur_id=administrateur.id)
    db.commit()


# --- Plan comptable applicable à une entreprise (référentiel + extensions) ---


@router.get(
    "/entreprises/{entreprise_id}/comptes",
    response_model=list[CompteLecture],
)
def lister_comptes_entreprise(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    recherche: str | None = None,
    classe: int | None = None,
    limite: int = 1000,
    decalage: int = 0,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte.consulter")),
    db: Session = Depends(get_db),
) -> list[CompteLecture]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    comptes = service.lister_comptes(
        actifs_seulement=actifs_seulement,
        recherche=recherche,
        classe=classe,
        limite=limite,
        decalage=decalage,
    )
    return [CompteLecture.model_validate(c) for c in comptes]


@router.get(
    "/entreprises/{entreprise_id}/comptes/collectifs",
    response_model=list[CompteLecture],
)
def lister_comptes_collectifs(
    entreprise_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte.consulter")),
    db: Session = Depends(get_db),
) -> list[CompteLecture]:
    """Les comptes éligibles comme compte collectif d'un tiers (module
    `tiers`, à venir)."""
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return [CompteLecture.model_validate(c) for c in service.lister_comptes_collectifs()]


@router.post(
    "/entreprises/{entreprise_id}/comptes",
    response_model=CompteLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_extension_compte(
    entreprise_id: uuid.UUID,
    donnees: CompteCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte.creer")),
    db: Session = Depends(get_db),
) -> CompteLecture:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    compte = service.creer_extension_compte(
        auteur_id=contexte.utilisateur_id,
        numero=donnees.numero,
        libelle=donnees.libelle,
        classe=donnees.classe,
        lettrable=donnees.lettrable,
        est_collectif=donnees.est_collectif,
        compte_parent_id=donnees.compte_parent_id,
    )
    db.commit()
    return CompteLecture.model_validate(compte)


@router.post(
    "/entreprises/{entreprise_id}/comptes/importer",
    response_model=CompteImportResultat,
    status_code=status.HTTP_201_CREATED,
)
def importer_comptes(
    entreprise_id: uuid.UUID,
    fichier: UploadFile = File(...),
    contexte: ContexteEntreprise = Depends(exiger_permission("compte.creer")),
    db: Session = Depends(get_db),
) -> CompteImportResultat:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    resultat = service.importer_comptes(
        auteur_id=contexte.utilisateur_id,
        contenu=fichier.file.read(),
        nom_fichier=fichier.filename or "",
    )
    db.commit()
    return CompteImportResultat(
        comptes_crees=[CompteLecture.model_validate(c) for c in resultat.comptes_crees],
        ignores=[
            {"numero": i.numero, "libelle": i.libelle, "raison": i.raison} for i in resultat.ignores
        ],
    )


@router.post(
    "/entreprises/{entreprise_id}/comptes/{compte_id}/desactiver",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desactiver_extension_compte(
    entreprise_id: uuid.UUID,
    compte_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("compte.archiver")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    service.desactiver_extension_compte(compte_id, auteur_id=contexte.utilisateur_id)
    db.commit()


# --- Journaux ------------------------------------------------------------------


@router.post(
    "/entreprises/{entreprise_id}/journaux",
    response_model=JournalLecture,
    status_code=status.HTTP_201_CREATED,
)
def creer_journal(
    entreprise_id: uuid.UUID,
    donnees: JournalCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal.creer")),
    db: Session = Depends(get_db),
) -> JournalLecture:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    journal = service.creer_journal(
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        libelle=donnees.libelle,
        type_journal=donnees.type_journal,
    )
    db.commit()
    return JournalLecture.model_validate(journal)


@router.get(
    "/entreprises/{entreprise_id}/journaux",
    response_model=list[JournalLecture],
)
def lister_journaux(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal.consulter")),
    db: Session = Depends(get_db),
) -> list[JournalLecture]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return [
        JournalLecture.model_validate(j)
        for j in service.lister_journaux(actifs_seulement=actifs_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/journaux/{journal_id}",
    response_model=JournalLecture,
)
def lire_journal(
    entreprise_id: uuid.UUID,
    journal_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal.consulter")),
    db: Session = Depends(get_db),
) -> JournalLecture:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return JournalLecture.model_validate(service.obtenir_journal(journal_id))


@router.post(
    "/entreprises/{entreprise_id}/journaux/{journal_id}/desactiver",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desactiver_journal(
    entreprise_id: uuid.UUID,
    journal_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("journal.archiver")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    service.desactiver_journal(journal_id, auteur_id=contexte.utilisateur_id)
    db.commit()


# --- Modèles d'écriture (saisie par modèle) -------------------------------


def _lignes_modele_avec(ecriture_service: ServiceComptabilite, modele: object) -> ModeleEcritureAvecLignes:
    lignes = ecriture_service.lister_lignes_modele(modele.id)
    return ModeleEcritureAvecLignes.model_validate(
        {**ModeleEcritureLecture.model_validate(modele).model_dump(), "lignes": lignes}
    )


@router.post(
    "/entreprises/{entreprise_id}/modeles-ecriture",
    response_model=ModeleEcritureAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def creer_modele(
    entreprise_id: uuid.UUID,
    donnees: ModeleEcritureCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("modele_ecriture.creer")),
    db: Session = Depends(get_db),
) -> ModeleEcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    modele = service.creer_modele(
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        libelle=donnees.libelle,
        journal_id=donnees.journal_id,
        lignes=[
            LigneModeleSaisie(compte_id=l.compte_id, sens=l.sens.value, libelle=l.libelle)
            for l in donnees.lignes
        ],
    )
    db.commit()
    return _lignes_modele_avec(service, modele)


@router.get(
    "/entreprises/{entreprise_id}/modeles-ecriture",
    response_model=list[ModeleEcritureAvecLignes],
)
def lister_modeles(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("modele_ecriture.consulter")),
    db: Session = Depends(get_db),
) -> list[ModeleEcritureAvecLignes]:
    # Avec lignes, pas juste l'en-tête : contrairement à la liste des
    # écritures (lourde, lignes chargées à la demande sur le détail), un
    # modèle sert justement à être "appliqué" depuis la liste elle-même
    # (voir ModelesEcritureListe.vue), ce qui a besoin des lignes tout de
    # suite — pas de round-trip supplémentaire pour un nombre de modèles
    # qui reste faible par entreprise.
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return [
        _lignes_modele_avec(service, m) for m in service.lister_modeles(actifs_seulement=actifs_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/modeles-ecriture/{modele_id}",
    response_model=ModeleEcritureAvecLignes,
)
def lire_modele(
    entreprise_id: uuid.UUID,
    modele_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("modele_ecriture.consulter")),
    db: Session = Depends(get_db),
) -> ModeleEcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    modele = service.obtenir_modele(modele_id)
    return _lignes_modele_avec(service, modele)


@router.patch(
    "/entreprises/{entreprise_id}/modeles-ecriture/{modele_id}",
    response_model=ModeleEcritureAvecLignes,
)
def modifier_modele(
    entreprise_id: uuid.UUID,
    modele_id: uuid.UUID,
    donnees: ModeleEcritureMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("modele_ecriture.modifier")),
    db: Session = Depends(get_db),
) -> ModeleEcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    modele = service.modifier_modele(
        modele_id,
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        libelle=donnees.libelle,
        journal_id=donnees.journal_id,
        actif=donnees.actif,
        lignes=(
            [
                LigneModeleSaisie(compte_id=l.compte_id, sens=l.sens.value, libelle=l.libelle)
                for l in donnees.lignes
            ]
            if donnees.lignes is not None
            else None
        ),
    )
    db.commit()
    return _lignes_modele_avec(service, modele)


@router.post(
    "/entreprises/{entreprise_id}/modeles-ecriture/{modele_id}/appliquer",
    response_model=EcritureAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def appliquer_modele(
    entreprise_id: uuid.UUID,
    modele_id: uuid.UUID,
    donnees: AppliquerModeleDonnees,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.creer")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.appliquer_modele(
        modele_id,
        auteur_id=contexte.utilisateur_id,
        exercice_id=donnees.exercice_id,
        date_ecriture=donnees.date_ecriture,
        libelle=donnees.libelle,
        reference_piece=donnees.reference_piece,
        montants=[
            MontantLigneModele(ligne_modele_id=l.ligne_modele_id, montant=l.montant)
            for l in donnees.lignes
        ],
    )
    db.commit()
    lignes = service.lister_lignes(ecriture.id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(ecriture).model_dump(), "lignes": lignes}
    )


# --- Écritures récurrentes --------------------------------------------------


def _lignes_recurrentes_avec(
    service: ServiceComptabilite, recurrente: object
) -> EcritureRecurrenteAvecLignes:
    lignes = service.lister_lignes_ecriture_recurrente(recurrente.id)
    return EcritureRecurrenteAvecLignes.model_validate(
        {**EcritureRecurrenteLecture.model_validate(recurrente).model_dump(), "lignes": lignes}
    )


def _lignes_recurrence_saisies(donnees_lignes: list) -> list[LigneEcritureRecurrenteSaisie]:
    return [
        LigneEcritureRecurrenteSaisie(
            compte_id=ligne.compte_id,
            sens=ligne.sens.value,
            montant=ligne.montant,
            libelle=ligne.libelle,
        )
        for ligne in donnees_lignes
    ]


@router.post(
    "/entreprises/{entreprise_id}/ecritures-recurrentes",
    response_model=EcritureRecurrenteAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def creer_ecriture_recurrente(
    entreprise_id: uuid.UUID,
    donnees: EcritureRecurrenteCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture_recurrente.creer")),
    db: Session = Depends(get_db),
) -> EcritureRecurrenteAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    recurrente = service.creer_ecriture_recurrente(
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        libelle=donnees.libelle,
        journal_id=donnees.journal_id,
        periodicite=donnees.periodicite,
        date_debut=donnees.date_debut,
        date_fin=donnees.date_fin,
        reference_piece=donnees.reference_piece,
        lignes=_lignes_recurrence_saisies(donnees.lignes),
    )
    db.commit()
    return _lignes_recurrentes_avec(service, recurrente)


@router.get(
    "/entreprises/{entreprise_id}/ecritures-recurrentes",
    response_model=list[EcritureRecurrenteAvecLignes],
)
def lister_ecritures_recurrentes(
    entreprise_id: uuid.UUID,
    actifs_seulement: bool = True,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture_recurrente.consulter")),
    db: Session = Depends(get_db),
) -> list[EcritureRecurrenteAvecLignes]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return [
        _lignes_recurrentes_avec(service, r)
        for r in service.lister_ecritures_recurrentes(actifs_seulement=actifs_seulement)
    ]


@router.get(
    "/entreprises/{entreprise_id}/ecritures-recurrentes/{ecriture_recurrente_id}",
    response_model=EcritureRecurrenteAvecLignes,
)
def lire_ecriture_recurrente(
    entreprise_id: uuid.UUID,
    ecriture_recurrente_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture_recurrente.consulter")),
    db: Session = Depends(get_db),
) -> EcritureRecurrenteAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    recurrente = service.obtenir_ecriture_recurrente(ecriture_recurrente_id)
    return _lignes_recurrentes_avec(service, recurrente)


@router.patch(
    "/entreprises/{entreprise_id}/ecritures-recurrentes/{ecriture_recurrente_id}",
    response_model=EcritureRecurrenteAvecLignes,
)
def modifier_ecriture_recurrente(
    entreprise_id: uuid.UUID,
    ecriture_recurrente_id: uuid.UUID,
    donnees: EcritureRecurrenteMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture_recurrente.modifier")),
    db: Session = Depends(get_db),
) -> EcritureRecurrenteAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    recurrente = service.modifier_ecriture_recurrente(
        ecriture_recurrente_id,
        auteur_id=contexte.utilisateur_id,
        code=donnees.code,
        libelle=donnees.libelle,
        journal_id=donnees.journal_id,
        periodicite=donnees.periodicite,
        date_fin=donnees.date_fin,
        reference_piece=donnees.reference_piece,
        actif=donnees.actif,
        lignes=(_lignes_recurrence_saisies(donnees.lignes) if donnees.lignes is not None else None),
    )
    db.commit()
    return _lignes_recurrentes_avec(service, recurrente)


@router.post(
    "/entreprises/{entreprise_id}/ecritures-recurrentes/{ecriture_recurrente_id}/generer",
    response_model=GenerationEcheancesResultat,
)
def generer_echeances(
    entreprise_id: uuid.UUID,
    ecriture_recurrente_id: uuid.UUID,
    donnees: GenerationEcheancesDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture_recurrente.generer")),
    db: Session = Depends(get_db),
) -> GenerationEcheancesResultat:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    resultat = service.generer_echeances(
        ecriture_recurrente_id,
        auteur_id=contexte.utilisateur_id,
        jusquau=donnees.jusquau,
    )
    db.commit()
    return GenerationEcheancesResultat(
        ecritures_creees=[EcritureLecture.model_validate(e) for e in resultat.ecritures_creees],
        ignorees=[
            EcheanceIgnoreeLecture(date_echeance=i.date_echeance, raison=i.raison)
            for i in resultat.ignorees
        ],
    )


# --- Écritures -------------------------------------------------------------


def _lignes_saisies(donnees_lignes: list) -> list[LigneSaisie]:
    return [
        LigneSaisie(
            compte_id=ligne.compte_id,
            debit=ligne.debit,
            credit=ligne.credit,
            tiers_id=ligne.tiers_id,
            libelle=ligne.libelle,
            date_echeance=ligne.date_echeance,
        )
        for ligne in donnees_lignes
    ]


@router.post(
    "/entreprises/{entreprise_id}/ecritures",
    response_model=EcritureAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def creer_ecriture(
    entreprise_id: uuid.UUID,
    donnees: EcritureCreation,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.creer")),
    _autorisation_validation: ContexteEntreprise = Depends(exiger_permission("ecriture.valider")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    """Saisie manuelle : l'écriture est créée ET validée en une seule étape
    (voir `ServiceComptabilite.creer_ecriture_validee`) — d'où les deux
    permissions requises : `ecriture.creer` et `ecriture.valider`."""
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.creer_ecriture_validee(
        auteur_id=contexte.utilisateur_id,
        journal_id=donnees.journal_id,
        exercice_id=donnees.exercice_id,
        date_ecriture=donnees.date_ecriture,
        libelle=donnees.libelle,
        reference_piece=donnees.reference_piece,
        lignes=_lignes_saisies(donnees.lignes),
    )
    db.commit()
    lignes = service.lister_lignes(ecriture.id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(ecriture).model_dump(), "lignes": lignes}
    )


@router.post(
    "/entreprises/{entreprise_id}/ecritures/importer",
    response_model=EcritureImportResultat,
    status_code=status.HTTP_201_CREATED,
)
def importer_ecritures(
    entreprise_id: uuid.UUID,
    fichier: UploadFile = File(...),
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.creer")),
    db: Session = Depends(get_db),
) -> EcritureImportResultat:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    resultat = service.importer_ecritures(
        auteur_id=contexte.utilisateur_id,
        contenu=fichier.file.read(),
        nom_fichier=fichier.filename or "",
    )
    db.commit()
    ecritures_avec_lignes = []
    for ecriture in resultat.ecritures_creees:
        lignes = service.lister_lignes(ecriture.id)
        ecritures_avec_lignes.append(
            EcritureAvecLignes.model_validate(
                {**EcritureLecture.model_validate(ecriture).model_dump(), "lignes": lignes}
            )
        )
    return EcritureImportResultat(
        ecritures_creees=ecritures_avec_lignes,
        ignorees=[
            {"journal": i.journal, "date": i.date, "piece": i.piece, "raison": i.raison}
            for i in resultat.ignorees
        ],
    )


@router.get(
    "/entreprises/{entreprise_id}/ecritures",
    response_model=list[EcritureLecture],
)
def lister_ecritures(
    entreprise_id: uuid.UUID,
    journal_id: uuid.UUID | None = None,
    exercice_id: uuid.UUID | None = None,
    statut: str | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.consulter")),
    db: Session = Depends(get_db),
) -> list[EcritureLecture]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecritures = service.lister_ecritures(
        journal_id=journal_id, exercice_id=exercice_id, statut=statut
    )
    return [EcritureLecture.model_validate(e) for e in ecritures]


@router.get(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}",
    response_model=EcritureAvecLignes,
)
def lire_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.consulter")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.obtenir_ecriture(ecriture_id)
    lignes = service.lister_lignes(ecriture_id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(ecriture).model_dump(), "lignes": lignes}
    )


@router.patch(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}",
    response_model=EcritureAvecLignes,
)
def modifier_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    donnees: EcritureMiseAJour,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.modifier")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.modifier_ecriture(
        ecriture_id,
        auteur_id=contexte.utilisateur_id,
        date_ecriture=donnees.date_ecriture,
        libelle=donnees.libelle,
        reference_piece=donnees.reference_piece,
        lignes=_lignes_saisies(donnees.lignes) if donnees.lignes is not None else None,
    )
    db.commit()
    lignes = service.lister_lignes(ecriture.id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(ecriture).model_dump(), "lignes": lignes}
    )


@router.post(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}/supprimer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.supprimer")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    service.supprimer_ecriture(ecriture_id, auteur_id=contexte.utilisateur_id)
    db.commit()


@router.post(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}/valider",
    response_model=EcritureLecture,
)
def valider_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.valider")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.valider_ecriture(ecriture_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return EcritureLecture.model_validate(ecriture)


@router.post(
    "/entreprises/{entreprise_id}/exercices/{exercice_id}/a-nouveaux",
    response_model=EcritureLecture,
    status_code=status.HTTP_201_CREATED,
)
def generer_a_nouveaux(
    entreprise_id: uuid.UUID,
    exercice_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.creer")),
    db: Session = Depends(get_db),
) -> EcritureLecture:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    ecriture = service.generer_a_nouveaux(exercice_id, auteur_id=contexte.utilisateur_id)
    db.commit()
    return EcritureLecture.model_validate(ecriture)


@router.post(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}/dupliquer",
    response_model=EcritureAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def dupliquer_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    donnees: EcritureDuplication,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.creer")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    copie = service.dupliquer_ecriture(
        ecriture_id,
        auteur_id=contexte.utilisateur_id,
        date_ecriture=donnees.date_ecriture,
        exercice_id=donnees.exercice_id,
        libelle=donnees.libelle,
    )
    db.commit()
    lignes = service.lister_lignes(copie.id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(copie).model_dump(), "lignes": lignes}
    )


@router.post(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}/extourner",
    response_model=EcritureAvecLignes,
    status_code=status.HTTP_201_CREATED,
)
def extourner_ecriture(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    donnees: EcritureExtourne,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.annuler")),
    db: Session = Depends(get_db),
) -> EcritureAvecLignes:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    nouvelle = service.extourner_ecriture(
        ecriture_id,
        auteur_id=contexte.utilisateur_id,
        date_ecriture=donnees.date_ecriture,
        libelle=donnees.libelle,
    )
    db.commit()
    lignes = service.lister_lignes(nouvelle.id)
    return EcritureAvecLignes.model_validate(
        {**EcritureLecture.model_validate(nouvelle).model_dump(), "lignes": lignes}
    )


@router.get(
    "/entreprises/{entreprise_id}/ecritures/{ecriture_id}/extournant",
    response_model=list[EcritureLecture],
)
def lister_extournant(
    entreprise_id: uuid.UUID,
    ecriture_id: uuid.UUID,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.consulter")),
    db: Session = Depends(get_db),
) -> list[EcritureLecture]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    return [EcritureLecture.model_validate(e) for e in service.lister_extournant(ecriture_id)]


# --- Lettrage manuel (comptes généraux / tiers) -----------------------------


@router.get(
    "/entreprises/{entreprise_id}/comptes/{compte_id}/lignes-lettrage",
    response_model=list[LigneLettrageLecture],
)
def lister_lignes_lettrage(
    entreprise_id: uuid.UUID,
    compte_id: uuid.UUID,
    tiers_id: uuid.UUID | None = None,
    lettrees: bool | None = None,
    contexte: ContexteEntreprise = Depends(exiger_permission("ecriture.consulter")),
    db: Session = Depends(get_db),
) -> list[LigneLettrageLecture]:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    lignes = service.lister_lignes_lettrage(compte_id, tiers_id=tiers_id, lettrees=lettrees)
    return [LigneLettrageLecture.model_validate(l) for l in lignes]


@router.post(
    "/entreprises/{entreprise_id}/lettrages",
    response_model=LettrageReponse,
    status_code=status.HTTP_201_CREATED,
)
def lettrer(
    entreprise_id: uuid.UUID,
    donnees: LettrageDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("lettrage.creer")),
    db: Session = Depends(get_db),
) -> LettrageReponse:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    code = service.lettrer(auteur_id=contexte.utilisateur_id, ligne_ecriture_ids=donnees.ligne_ecriture_ids)
    db.commit()
    return LettrageReponse(code_lettrage=code)


@router.post(
    "/entreprises/{entreprise_id}/lettrages/annuler",
    status_code=status.HTTP_204_NO_CONTENT,
)
def annuler_lettrage(
    entreprise_id: uuid.UUID,
    donnees: DelettrageDemande,
    contexte: ContexteEntreprise = Depends(exiger_permission("lettrage.annuler")),
    db: Session = Depends(get_db),
) -> None:
    service = ServiceComptabilite(db, contexte.entreprise_id)
    service.delettrer(donnees.code_lettrage, auteur_id=contexte.utilisateur_id)
    db.commit()