"""
Output Exporter module.
Saves extracted company profiles into structured output.json and flattened output.csv.
"""

import csv
import json
import logging
from pathlib import Path
from typing import List

from schema import CompanyProfile

logger = logging.getLogger(__name__)


class OutputExporter:
    """
    Exports CompanyProfile results to JSON and CSV formats.
    """

    def __init__(self, output_dir: Path = Path("output")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, profiles: List[CompanyProfile], filename: str = "output.json") -> Path:
        """Exports profiles to formatted JSON."""
        file_path = self.output_dir / filename
        data = [p.model_dump() for p in profiles]
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Exported {len(profiles)} profiles to {file_path}")
        return file_path

    def export_csv(self, profiles: List[CompanyProfile], filename: str = "output.csv") -> Path:
        """Exports profiles to flattened CSV."""
        file_path = self.output_dir / filename

        fieldnames = [
            "domain",
            "company_overview",
            "target_audience",
            "contact_emails",
            "team_members",
            "confidence_score",
            "pages_scraped_count",
            "tokens_used",
            "estimated_cost_usd",
        ]

        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for p in profiles:
                emails_str = "; ".join(p.contact_emails)
                team_list = []
                for m in p.team_members:
                    link = f" ({m.linkedin_url})" if m.linkedin_url else ""
                    team_list.append(f"{m.name}: {m.role}{link}")
                team_str = " | ".join(team_list)

                writer.writerow(
                    {
                        "domain": p.domain,
                        "company_overview": p.company_overview,
                        "target_audience": p.target_audience,
                        "contact_emails": emails_str,
                        "team_members": team_str,
                        "confidence_score": f"{p.confidence_score:.2f}",
                        "pages_scraped_count": len(p.pages_scraped),
                        "tokens_used": p.tokens_used,
                        "estimated_cost_usd": f"${p.estimated_cost_usd:.5f}",
                    }
                )

        logger.info(f"Exported {len(profiles)} profiles to {file_path}")
        return file_path

    def export_all(self, profiles: List[CompanyProfile]):
        """Exports both JSON and CSV deliverables."""
        json_path = self.export_json(profiles)
        csv_path = self.export_csv(profiles)
        return json_path, csv_path
