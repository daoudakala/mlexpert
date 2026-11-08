"""Modèle du module auth.

Une seule table, `SessionUtilisateur` : un jeton de rafraîchissement
révocable par appareil (cahier des charges, section 27 : "gestion des
sessions"). Le profil de l'utilisateur (`Utilisateur`) et sa mécanique de
connexion vivent dans deux modules distincts, comme prévu dès le début du
socle.

Contrairement à `JournalActivite`, cette table EST modifiable après
création : une session se révoque (`revoque_le` passe de nul à une date).
`HorodatageMixin` garde donc son sens ici — `modifie_le` avance à la
révocation.

Le jeton lui-même n'est jamais stocké en clair, seule son empreinte
(`core/security.hash_token`) l'est — voir `core/security.py`, déjà écrit :
si la base fuit, aucun jeton n'est directement réutilisable.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base
from app.shared.mixins import HorodatageMixin, IdentifiantMixin


class SessionUtilisateur(IdentifiantMixin, HorodatageMixin, Base):
    __tablename__ = "sessions_utilisateur"

    utilisateur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Empreinte SHA-256 du jeton de rafraîchissement (jamais le jeton en
    # clair). Unique : deux sessions ne peuvent pas partager une empreinte.
    jeton_hache: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    appareil: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adresse_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoque_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    derniere_utilisation_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def est_active(self) -> bool:
        return self.revoque_le is None and self.expire_le > datetime.now(timezone.utc)