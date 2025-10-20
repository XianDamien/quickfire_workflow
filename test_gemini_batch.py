#!/usr/bin/env python3
"""
Batch test script for Gemini evaluation with Qwen ASR data
Tests all students in archive/Zoe41900-9.8 with evaluation_v1 prompt.
Outputs v1 versioned results for debugging and comparison.
Uses gemini-2.0-flash API for multi-modal evaluation.
"""

import os
import sys
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
ARCHIVE_DIR = Path(__file__).parent / 'archive' / 'Zoe41900-9.8'
SHARED_CONTEXT_DIR = ARCHIVE_DIR / '_shared_context'
PROMPTS_DIR = Path(__file__).parent / 'prompts'
OUTPUT_BASE_DIR = Path(__file__).parent / 'test_outputs_v1'

# Students to process
STUDENTS = ['Cathy', 'Frances Wang', 'Lucy', 'Oscar', 'Rico', 'Yoyo']

# Evaluation prompt (v1)
EVAL_PROMPT_PATH = PROMPTS_DIR / 'evaluation_v1.txt'

# Vocabulary/question bank
QB_PATH = SHARED_CONTEXT_DIR / 'R1-65.csv'


def load_evaluation_prompt() -> str:
    """Load the evaluation v1 prompt."""
    if not EVAL_PROMPT_PATH.exists():
        raise FileNotFoundError(f"Evaluation prompt not found: {EVAL_PROMPT_PATH}")

    with open(EVAL_PROMPT_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def load_asr_data(asr_path: Path) -> dict:
    """Load ASR intermediate raw data."""
    if not asr_path.exists():
        logger.warning(f"ASR file not found: {asr_path}")
        return None

    with open(asr_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_vocabulary(qb_path: Path) -> dict:
    """Load vocabulary from JSON file (named .csv but actually JSON)."""
    if not qb_path.exists():
        raise FileNotFoundError(f"Vocabulary file not found: {qb_path}")

    with open(qb_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Try to parse as JSON
        vocab = json.loads(content)

    return vocab


def build_prompt(eval_template: str, vocabulary: dict, asr_data: dict) -> str:
    """Build the complete prompt with vocabulary and ASR data."""
    # For now, we'll use a simplified approach that inserts vocabulary and ASR
    # This would need to be customized based on the actual prompt template structure

    prompt = eval_template

    # Insert vocabulary if template has placeholder
    if "{{vocabulary.json}}" in prompt:
        prompt = prompt.replace("{{vocabulary.json}}", json.dumps(vocabulary, ensure_ascii=False, indent=2))

    # Append ASR data at the end
    if asr_data:
        prompt += "\n\n2. ASR转写结果 (机器初步识别)\n"
        prompt += json.dumps(asr_data, ensure_ascii=False, indent=2)

    return prompt


def initialize_gemini_client(api_key: str) -> Any:
    """Initialize Gemini client using google.generativeai library."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        logger.info("✅ Initialized google.generativeai client")
        return genai
    except ImportError as e:
        logger.error(f"❌ google.generativeai not available: {e}")
        sys.exit(1)


def process_student(
    genai: Any,
    student_name: str,
    eval_template: str,
    vocabulary: dict,
    output_dir: Path
) -> dict:
    """Process a single student."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing student: {student_name}")
    logger.info(f"{'='*60}")

    student_dir = ARCHIVE_DIR / student_name
    if not student_dir.exists():
        logger.error(f"❌ Student directory not found: {student_dir}")
        return {
            'student': student_name,
            'status': 'error',
            'error': 'Student directory not found'
        }

    # Find audio and ASR files
    audio_files = list(student_dir.glob('1_input_audio.mp3'))
    asr_files = list(student_dir.glob('2_intermediate_asr_raw.json'))

    if not asr_files:
        logger.warning(f"⏭️ No ASR file found for {student_name}")
        return {
            'student': student_name,
            'status': 'skip',
            'error': 'No ASR file found'
        }

    audio_path = audio_files[0] if audio_files else None
    asr_path = asr_files[0]

    logger.info(f"📁 Audio: {audio_path.name if audio_path else 'None'}")
    logger.info(f"📁 ASR: {asr_path.name}")

    # Load ASR data
    asr_data = load_asr_data(asr_path)
    if not asr_data:
        return {
            'student': student_name,
            'status': 'error',
            'error': 'Failed to load ASR data'
        }

    # Build prompt
    prompt = build_prompt(eval_template, vocabulary, asr_data)
    logger.info(f"📝 Prompt length: {len(prompt)} characters")

    # Call Gemini API
    logger.info("🔄 Calling Gemini API...")
    try:
        # Prepare content with audio if available
        content_parts = [prompt]

        if audio_path and audio_path.exists():
            logger.info(f"🎵 Attaching audio file: {audio_path}")
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            content_parts.append({
                "mime_type": "audio/mpeg",
                "data": audio_data
            })

        # Use Gemini 2.0 Flash model
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction="你是一个专业的AI语言教师助教。按输入的题库、ASR结果和音频进行评测。严格遵循评分规则，只输出一个JSON对象，不要包含任何多余文本。"
        )

        # Generate response
        response = model.generate_content(
            content_parts,
            generation_config={"response_mime_type": "application/json"}
        )

        # Parse response
        response_text = response.text.strip()
        logger.info(f"📨 Received response ({len(response_text)} chars)")

        # Clean and parse JSON
        result = json.loads(response_text)
        logger.info("✅ Successfully parsed JSON response")

        # Save output
        output_file = output_dir / f"{student_name.replace(' ', '_')}_v1_result.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Result saved to: {output_file}")

        # Extract grades if available
        grade = result.get('final_grade_suggestion', 'N/A')
        hard_errors = result.get('mistake_count', {}).get('hard_errors', 'N/A')
        soft_errors = result.get('mistake_count', {}).get('soft_errors', 'N/A')

        logger.info(f"📊 Grade: {grade} | Hard errors: {hard_errors} | Soft errors: {soft_errors}")

        # Add delay between requests (respect rate limits)
        time.sleep(2)

        return {
            'student': student_name,
            'status': 'success',
            'output_file': str(output_file),
            'grade': grade,
            'hard_errors': hard_errors,
            'soft_errors': soft_errors
        }

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error for {student_name}: {str(e)}")
        return {
            'student': student_name,
            'status': 'error',
            'error': f"JSON parse error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"❌ Error processing {student_name}: {str(e)}", exc_info=True)
        return {
            'student': student_name,
            'status': 'error',
            'error': str(e)
        }


def main():
    """Main test function."""
    logger.info("\n" + "="*60)
    logger.info("🚀 Starting Gemini batch evaluation for Zoe41900-9.8")
    logger.info("="*60)
    logger.info(f"📁 Archive directory: {ARCHIVE_DIR}")
    logger.info(f"📁 Output directory: {OUTPUT_BASE_DIR}")

    # Check prerequisites
    if not ARCHIVE_DIR.exists():
        logger.error(f"❌ Archive directory not found: {ARCHIVE_DIR}")
        return

    if not QB_PATH.exists():
        logger.error(f"❌ Question bank file not found: {QB_PATH}")
        return

    if not EVAL_PROMPT_PATH.exists():
        logger.error(f"❌ Evaluation prompt not found: {EVAL_PROMPT_PATH}")
        return

    # Load evaluation prompt and vocabulary
    logger.info("📖 Loading evaluation prompt...")
    eval_template = load_evaluation_prompt()

    logger.info("📖 Loading vocabulary from CSV...")
    vocabulary = load_vocabulary(QB_PATH)
    logger.info(f"✅ Loaded {len(vocabulary)} vocabulary items")

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.error("❌ GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")
        logger.error("   Set with: export GEMINI_API_KEY='your-key'")
        return

    logger.info(f"🔑 Using API key: {api_key[:15]}...")

    # Initialize client
    logger.info("⚙️ Initializing Gemini client...")
    genai = initialize_gemini_client(api_key)

    # Process each student
    results = []
    for i, student_name in enumerate(STUDENTS, 1):
        logger.info(f"\n⏳ Processing {i}/{len(STUDENTS)}: {student_name}")
        result = process_student(
            genai,
            student_name,
            eval_template,
            vocabulary,
            OUTPUT_BASE_DIR
        )
        results.append(result)

    # Summary report
    logger.info(f"\n{'='*60}")
    logger.info("📊 EVALUATION SUMMARY")
    logger.info(f"{'='*60}")

    summary = {
        'timestamp': datetime.now().isoformat(),
        'model': 'gemini-2.0-flash',
        'total_students': len(STUDENTS),
        'results': results,
        'statistics': {
            'success': sum(1 for r in results if r['status'] == 'success'),
            'error': sum(1 for r in results if r['status'] == 'error'),
            'skip': sum(1 for r in results if r['status'] == 'skip')
        }
    }

    # Save summary
    summary_file = OUTPUT_BASE_DIR / 'test_summary_v1.json'
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(f"\n📈 Statistics: {summary['statistics']}")
    logger.info(f"💾 Summary saved to: {summary_file}")

    # Print detailed results
    logger.info(f"\n{'Student':<20} {'Status':<10} {'Grade':<6} {'Hard':<5} {'Soft':<5} {'Details'}")
    logger.info("-" * 80)

    for result in results:
        status_icon = {
            'success': '✅',
            'error': '❌',
            'skip': '⏭️'
        }.get(result['status'], '❓')

        status_text = result['status'].upper()

        if result['status'] == 'success':
            grade = result.get('grade', 'N/A')
            hard = result.get('hard_errors', 'N/A')
            soft = result.get('soft_errors', 'N/A')
            logger.info(f"{status_icon} {result['student']:<18} {status_text:<10} {grade:<6} {str(hard):<5} {str(soft):<5}")
        else:
            error_msg = result.get('error', 'Unknown error')[:40]
            logger.info(f"{status_icon} {result['student']:<18} {status_text:<10} {error_msg}")

    logger.info(f"\n✅ Batch evaluation complete!")
    logger.info(f"📁 Results saved to: {OUTPUT_BASE_DIR}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
