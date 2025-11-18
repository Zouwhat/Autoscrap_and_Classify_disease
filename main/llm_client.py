"""
LLM Client for Epic1_3 Pipeline
Unified client สำหรับ Typhoon และ Ollama
"""

import requests
import json
import time
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Exception raised when LLM client encounters an error"""
    pass


@dataclass
class LLMResponse:
    """LLM response container"""
    content: str
    provider: str
    model: str
    response_time_ms: int
    success: bool
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class BaseLLMClient:
    """Base class for LLM clients"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM client

        Args:
            config: LLM configuration dict
        """
        self.config = config
        self.provider = config.get('provider', 'unknown')
        self.model = config['model']
        self.temperature = config.get('temperature', 0.1)
        self.max_tokens = config.get('max_tokens', 500)
        self.timeout = config.get('timeout_seconds', 45)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay_seconds', 2.0)

        logger.info(f"[OK] {self.provider.upper()} client initialized: {self.model}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate response from LLM

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            LLMResponse object
        """
        raise NotImplementedError("Subclass must implement generate()")

    def _retry_request(self, request_func, *args, **kwargs) -> Any:
        """
        Retry request with exponential backoff

        Args:
            request_func: Function to call
            *args, **kwargs: Arguments for request_func

        Returns:
            Result from request_func

        Raises:
            LLMClientError: If all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return request_func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} retries failed: {e}")

        raise LLMClientError(f"Request failed after {self.max_retries} retries: {last_error}")


class TyphoonClient(BaseLLMClient):
    """Typhoon API client"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Typhoon client"""
        super().__init__(config)

        # Get API key from environment
        api_key_env = config.get('api_key_env', 'TYPHOON_API_KEY')
        self.api_key = os.getenv(api_key_env)

        if not self.api_key:
            raise LLMClientError(f"Typhoon API key not found in environment variable: {api_key_env}")

        self.base_url = config.get('base_url', 'https://api.opentyphoon.ai/v1/chat/completions')
        logger.info(f"[OK] Typhoon client ready: {self.base_url}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response from Typhoon API"""

        def _make_request():
            start_time = time.time()

            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature if temperature is not None else self.temperature,
                'max_tokens': max_tokens if max_tokens is not None else self.max_tokens
            }

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            if response.status_code != 200:
                error_msg = f"Typhoon API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return LLMResponse(
                    content="",
                    provider=self.provider,
                    model=self.model,
                    response_time_ms=response_time_ms,
                    success=False,
                    error=error_msg
                )

            result = response.json()
            content = result['choices'][0]['message']['content'].strip()

            return LLMResponse(
                content=content,
                provider=self.provider,
                model=self.model,
                response_time_ms=response_time_ms,
                success=True,
                raw_response=result
            )

        try:
            return self._retry_request(_make_request)
        except Exception as e:
            return LLMResponse(
                content="",
                provider=self.provider,
                model=self.model,
                response_time_ms=0,
                success=False,
                error=str(e)
            )


class OllamaClient(BaseLLMClient):
    """Ollama local client"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Ollama client"""
        super().__init__(config)

        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.chat_endpoint = f"{self.base_url}/api/chat"

        # Test connection
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info(f"[OK] Ollama server connected: {self.base_url}")
            else:
                logger.warning(f"[WARN] Ollama server returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"[WARN] Cannot connect to Ollama server: {e}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate response from Ollama"""

        def _make_request():
            start_time = time.time()

            payload = {
                'model': self.model,
                'messages': messages,
                'stream': False,
                'options': {
                    'temperature': temperature if temperature is not None else self.temperature,
                    'num_predict': max_tokens if max_tokens is not None else self.max_tokens
                }
            }

            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=self.timeout
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            if response.status_code != 200:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return LLMResponse(
                    content="",
                    provider=self.provider,
                    model=self.model,
                    response_time_ms=response_time_ms,
                    success=False,
                    error=error_msg
                )

            result = response.json()
            content = result['message']['content'].strip()

            return LLMResponse(
                content=content,
                provider=self.provider,
                model=self.model,
                response_time_ms=response_time_ms,
                success=True,
                raw_response=result
            )

        try:
            return self._retry_request(_make_request)
        except Exception as e:
            return LLMResponse(
                content="",
                provider=self.provider,
                model=self.model,
                response_time_ms=0,
                success=False,
                error=str(e)
            )


class LLMClient:
    """
    Unified LLM client that supports multiple providers

    Automatically selects the correct client based on config
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM client

        Args:
            config: LLM configuration dict with 'provider' key
        """
        self.config = config
        self.provider = config['provider']

        # Create appropriate client
        if self.provider == 'typhoon':
            self.client = TyphoonClient(config)
        elif self.provider == 'ollama':
            self.client = OllamaClient(config)
        else:
            raise LLMClientError(f"Unsupported LLM provider: {self.provider}")

        logger.info(f"[OK] LLM Client initialized: {self.provider}")

    def generate(
        self,
        system_message: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate response from LLM

        Args:
            system_message: System prompt
            user_message: User prompt
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            LLMResponse object
        """
        messages = [
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': user_message}
        ]

        return self.client.generate(messages, temperature, max_tokens)

    def classify(self, system_message: str, content: str) -> Tuple[int, LLMResponse]:
        """
        Classify content (0 or 1)

        Args:
            system_message: System prompt for classification
            content: Content to classify

        Returns:
            Tuple of (prediction, LLMResponse)
        """
        response = self.generate(system_message, content)

        if not response.success:
            logger.error(f"Classification failed: {response.error}")
            return 0, response

        # Parse response (expecting 0 or 1)
        content_clean = response.content.strip()

        # Extract first digit
        for char in content_clean:
            if char in ['0', '1']:
                prediction = int(char)
                logger.debug(f"Classification: {prediction} ({response.response_time_ms}ms)")
                return prediction, response

        logger.warning(f"Could not parse classification result: {content_clean}")
        return 0, response

    def extract_json(self, system_message: str, content: str) -> Tuple[Optional[Dict], LLMResponse]:
        """
        Extract structured data as JSON

        Args:
            system_message: System prompt for extraction
            content: Content to extract from

        Returns:
            Tuple of (extracted_dict, LLMResponse)
        """
        response = self.generate(system_message, content)

        if not response.success:
            logger.error(f"Extraction failed: {response.error}")
            return None, response

        # Parse JSON from response
        try:
            # Try to find JSON in response
            content_clean = response.content.strip()

            # Remove markdown code blocks if present
            if content_clean.startswith('```'):
                lines = content_clean.split('\n')
                content_clean = '\n'.join(lines[1:-1])

            # Parse JSON
            extracted_data = json.loads(content_clean)
            logger.debug(f"Extraction successful ({response.response_time_ms}ms)")
            return extracted_data, response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Response content: {response.content[:200]}...")
            return None, response

    def __repr__(self):
        """String representation"""
        return f"LLMClient(provider={self.provider}, model={self.client.model})"


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test with Ollama (comment out if not available)
    print("\n" + "="*60)
    print("🧪 LLM CLIENT TEST - OLLAMA")
    print("="*60)

    try:
        ollama_config = {
            'provider': 'ollama',
            'model': 'qwen2.5:3b',
            'base_url': 'http://localhost:11434',
            'temperature': 0.1,
            'max_tokens': 100,
            'timeout_seconds': 30,
            'max_retries': 2
        }

        client = LLMClient(ollama_config)
        print(f"\n{client}")

        # Test generate
        response = client.generate(
            system_message="คุณเป็นผู้ช่วยที่เป็นประโยชน์",
            user_message="สวัสดีครับ ทดสอบการเชื่อมต่อ"
        )

        print(f"\n[RESPONSE] Response:")
        print(f"   Success: {response.success}")
        print(f"   Content: {response.content[:100]}...")
        print(f"   Time: {response.response_time_ms}ms")

        # Test classification
        class_response = client.classify(
            system_message="จำแนกข่าว ตอบ 0 หรือ 1",
            content="ข่าวการเมืองวันนี้"
        )

        print(f"\n[CLASSIFY] Classification:")
        print(f"   Prediction: {class_response[0]}")
        print(f"   Time: {class_response[1].response_time_ms}ms")

    except LLMClientError as e:
        print(f"\n[ERROR] Error: {e}")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
