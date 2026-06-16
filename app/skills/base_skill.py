from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    name: str = "base"
    description: str = "Base skill"

    @abstractmethod
    async def analyze(self, url: str, page_data: dict, llm: Any) -> dict:
        """
        Analyze the webpage and return a result dict.

        Returns:
            dict with keys:
                score (float 0-10): quality score
                findings (list[str]): specific observations
                details (str): overall assessment paragraph
        """
        pass
