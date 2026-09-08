from abc import ABC, abstractmethod
from app.core.logging_config import logger


class EmailSender(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, body: str) -> None:
        ...


class ConsoleEmailSender(EmailSender):
    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info(f"[MOCK EMAIL] to={to} subject={subject} body={body}")


email_sender: EmailSender = ConsoleEmailSender()