"""
Qwen3-ASR provider for audio transcription with vocabulary context.
Uses custom vocabulary from manifest to improve ASR accuracy.
"""

import os
import json
import dashscope
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class QwenASRProvider:
    """Qwen3-ASR provider for audio transcription with custom vocabulary."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Qwen ASR provider.

        Args:
            api_key: DashScope API key. If None, uses DASHSCOPE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        self.model = "qwen3-asr-flash"

    @staticmethod
    def load_vocabulary(vocab_path: str) -> Dict[str, list]:
        """
        Load vocabulary from JSON file.
        Handles UTF-8 BOM if present.

        Args:
            vocab_path: Path to vocabulary JSON file

        Returns:
            Dictionary with vocabulary entries
        """
        with open(vocab_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

    @staticmethod
    def build_context_text(vocabulary: Dict[str, list]) -> str:
        """
        Build context text from vocabulary for ASR optimization.

        Args:
            vocabulary: Dictionary with vocabulary entries

        Returns:
            Formatted context text for ASR
        """
        # Extract English terms and Chinese meanings
        terms = []
        for key, values in vocabulary.items():
            if isinstance(values, list) and len(values) >= 2:
                chinese_term = values[0]
                english_term = values[1]
                terms.append(f"{chinese_term}({english_term})")

        # Create context string
        context = "Domain vocabulary: " + ", ".join(terms)
        return context

    def transcribe_audio(
        self,
        audio_path: str,
        vocabulary_path: Optional[str] = None,
        language: Optional[str] = None,
        enable_itn: bool = False,
        enable_lid: bool = True,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Qwen3-ASR with optional vocabulary context.

        Args:
            audio_path: Path or URL to audio file
            vocabulary_path: Optional path to vocabulary JSON file for context
            language: Optional language code (e.g., "zh" for Chinese)
            enable_itn: Enable inverse text normalization
            enable_lid: Enable language identification

        Returns:
            Response dictionary with transcription results
        """
        # Build vocabulary context if provided
        system_context = ""
        if vocabulary_path and os.path.exists(vocabulary_path):
            vocab = self.load_vocabulary(vocabulary_path)
            system_context = self.build_context_text(vocab)

        # Build ASR options
        asr_options = {
            "enable_itn": enable_itn,
            "enable_lid": enable_lid,
        }
        if language:
            asr_options["language"] = language

        # Build messages
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "text": system_context if system_context else "You are an ASR assistant. Transcribe the audio accurately."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {"audio": audio_path}
                ]
            }
        ]

        # Call ASR API
        response = dashscope.MultiModalConversation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            result_format="message",
            asr_options=asr_options
        )

        return response

    def transcribe_and_save(
        self,
        input_audio_path: str,
        output_dir: str,
        vocabulary_path: Optional[str] = None,
        output_filename: str = "5_qwen_asr_output.json",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio and save results to file.

        Args:
            input_audio_path: Path or URL to input audio
            output_dir: Directory to save output files
            vocabulary_path: Optional path to vocabulary JSON file
            output_filename: Name of output JSON file
            language: Optional language code

        Returns:
            Response dictionary with transcription results
        """
        # Transcribe audio
        response = self.transcribe_audio(
            audio_path=input_audio_path,
            vocabulary_path=vocabulary_path,
            language=language,
        )

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Save response
        output_path = os.path.join(output_dir, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)

        print(f"ASR transcription saved to: {output_path}")
        return response


def process_all_students():
    """Process all student audio files in archive directory."""
    # Set up paths
    project_root = Path(__file__).parent.parent
    archive_path = project_root / "archive"

    # Find all course folders
    course_folders = sorted([d for d in archive_path.iterdir() if d.is_dir() and not d.name.startswith("_")])

    print(f"Found {len(course_folders)} course folders")

    # Create provider
    provider = QwenASRProvider()

    total_processed = 0
    total_skipped = 0

    for course_folder in course_folders:
        print(f"\n{'='*60}")
        print(f"Processing course: {course_folder.name}")
        print(f"{'='*60}")

        # Find vocabulary file for this course
        shared_context = course_folder / "_shared_context"
        vocab_file = None

        if shared_context.exists():
            # Look for vocabulary.json first, then CSV files
            vocab_json = shared_context / "vocabulary.json"
            if vocab_json.exists():
                vocab_file = str(vocab_json)
            else:
                # Find first CSV file
                csv_files = list(shared_context.glob("*.csv"))
                if csv_files:
                    vocab_file = str(csv_files[0])

        # Find all student folders
        student_folders = sorted([d for d in course_folder.iterdir() if d.is_dir() and not d.name.startswith("_")])

        for student_folder in student_folders:
            input_audio = student_folder / "1_input_audio.mp3"

            # Check if audio file exists
            if not input_audio.exists():
                print(f"  ⊘ {student_folder.name}: No audio file found")
                total_skipped += 1
                continue

            output_filename = "2_qwen_asr.json"
            output_path = student_folder / output_filename

            # Skip if already processed
            if output_path.exists():
                print(f"  ✓ {student_folder.name}: Already processed (skipping)")
                total_skipped += 1
                continue

            try:
                print(f"  ⟳ {student_folder.name}: Processing audio...")

                # Transcribe with vocabulary context
                response = provider.transcribe_and_save(
                    input_audio_path=str(input_audio),
                    output_dir=str(student_folder),
                    vocabulary_path=vocab_file,
                    output_filename=output_filename,
                    language="zh",  # Chinese language
                )

                print(f"  ✓ {student_folder.name}: Saved to {output_filename}")
                total_processed += 1

            except Exception as e:
                print(f"  ✗ {student_folder.name}: Error - {str(e)}")
                total_skipped += 1

    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"Processed: {total_processed}, Skipped: {total_skipped}")
    print(f"{'='*60}")


def main():
    """Main entry point - process all students."""
    process_all_students()


if __name__ == "__main__":
    main()
