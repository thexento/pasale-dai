import json
import logging
import re
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings
from app.ai.schemas import GeminiActionResponse
from app.ai.prompts import build_sales_prompt

logger = logging.getLogger("pasale.ai")


class GeminiSalesAgent:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        # Standard v1beta generateContent endpoint
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def _clean_json_text(self, text: str) -> str:
        """Strip markdown ticks or text around the JSON object."""
        text = text.strip()
        # Remove ```json ... ``` blocks if generated
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            text = match.group(1).strip()
        # Find outer braces
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end + 1]
        return text

    async def _call_rest_api(self, prompt: str) -> str:
        """Calls Google Generative Language REST API using httpx."""
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Gemini API returned {response.status_code}: {response.text}")
                raise RuntimeError(f"Gemini API Error: {response.status_code}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No response candidates returned by Gemini API")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise ValueError("Empty candidate content from Gemini API")

            return parts[0].get("text", "")

    async def generate_sales_response(
        self,
        catalog_summary: List[Dict[str, Any]],
        user_summary: str,
        recent_messages: List[Dict[str, str]],
        current_order_state: Dict[str, Any],
        verified_payment_state: Dict[str, Any],
        user_input: str
    ) -> GeminiActionResponse:
        """Generates structured sales actions, with retry and graceful fallback."""
        prompt = build_sales_prompt(
            catalog_summary,
            user_summary,
            recent_messages,
            current_order_state,
            verified_payment_state,
            user_input
        )

        for attempt in range(2):
            try:
                raw_text = await self._call_rest_api(prompt)
                cleaned = self._clean_json_text(raw_text)
                parsed = json.loads(cleaned)
                return GeminiActionResponse(**parsed)
            except Exception as e:
                logger.warning(f"AI parse attempt {attempt + 1} failed: {e}")
                if attempt == 0:
                    prompt += "\nERROR: Your previous output was not valid JSON matching the required schema. Output strict JSON only."

        # Graceful fallback so Discord bot never crashes
        return GeminiActionResponse(
            message="Namaste! We are experiencing a brief technical delay. How can I assist you with our catalog today?",
            payment_required=False,
            payment_processed=False
        )