from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    name: str = "base"
    description: str = "Base skill"
    runs_first: bool = False  # set True to run before all other skills

    @abstractmethod
    async def analyze(self, url: str, page_data: dict, llm: Any, requirements: str = "") -> dict:
        """
        Analyze the webpage and return a result dict.

        Args:
            url: URL being tested
            page_data: parsed page data from BeautifulSoup extraction
            llm: LangChain LLM instance
            requirements: inferred requirements string from RequirementsSkill (may be empty)

        Returns:
            dict with keys:
                score (float 0-10): quality score
                findings (list[str]): specific observations
                details (str): overall assessment paragraph
        """
        pass
