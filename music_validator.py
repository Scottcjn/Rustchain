// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT
import os
import sqlite3
import wave
import json
from pathlib import Path
import re
import mutagen
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis

DB_PATH = 'rustchain.db'

class MusicValidator:
    def __init__(self):
        self.required_keywords = [
            'rustchain', 'rtc', 'proof of antiquity', 'vintage hardware', 
            '1 cpu = 1 vote', 'mining', 'proof-of-antiquity'
        ]
        self.supported_formats = ['.mp3', '.wav', '.flac', '.ogg', '.m4a']
        self.min_duration = 30  # seconds
        self.max_duration = 180  # 3 minutes
        
    def validate_submission(self, audio_path, lyrics_path=None, lyrics_text=None):
        """Main validation method for music bounty submissions"""
        results = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'metadata': {}
        }
        
        # Check audio file exists and format
        if not os.path.exists(audio_path):
            results['errors'].append(f"Audio file not found: {audio_path}")
            return results
            
        file_ext = Path(audio_path).suffix.lower()
        if file_ext not in self.supported_formats:
            results['errors'].append(f"Unsupported audio format: {file_ext}")
            return results
            
        # Check duration
        duration = self._get_audio_duration(audio_path)
        if duration is None:
            results['errors'].append("Could not determine audio duration")
            return results
            
        results['metadata']['duration'] = duration
        
        if duration < self.min_duration:
            results['errors'].append(f"Audio too short: {duration}s (minimum {self.min_duration}s)")
        elif duration > self.max_duration:
            results['errors'].append(f"Audio too long: {duration}s (maximum {self.max_duration}s)")
            
        # Get lyrics content
        lyrics_content = ""
        if lyrics_text:
            lyrics_content = lyrics_text
        elif lyrics_path and os.path.exists(lyrics_path):
            with open(lyrics_path, 'r', encoding='utf-8') as f:
                lyrics_content = f.read()
        else:
            results['warnings'].append("No lyrics provided - checking audio metadata for lyrics")
            lyrics_content = self._extract_lyrics_from_metadata(audio_path) or ""
            
        # Validate lyrics content
        keyword_matches = self._check_required_keywords(lyrics_content)
        results['metadata']['keyword_matches'] = keyword_matches
        results['metadata']['keywords_found'] = len(keyword_matches)
        
        if len(keyword_matches) < 2:
            results['errors'].append(f"Lyrics must reference at least 2 required keywords. Found: {keyword_matches}")
            
        # Check for originality markers
        originality_score = self._check_originality(lyrics_content)
        results['metadata']['originality_score'] = originality_score
        
        if originality_score < 0.3:
            results['warnings'].append("Lyrics appear to have low originality - ensure this is original work")
            
        # Final validation
        if not results['errors']:
            results['valid'] = True
            
        return results
        
    def _get_audio_duration(self, audio_path):
        """Get duration of audio file in seconds"""
        try:
            file_ext = Path(audio_path).suffix.lower()
            
            if file_ext == '.wav':
                with wave.open(audio_path, 'r') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    return frames / float(rate)
            else:
                audio_file = mutagen.File(audio_path)
                if audio_file is not None:
                    return audio_file.info.length
        except Exception as e:
            print(f"Error getting duration for {audio_path}: {e}")
            
        return None
        
    def _check_required_keywords(self, text):
        """Check which required keywords are present in text"""
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.required_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
                
        return found_keywords
        
    def _extract_lyrics_from_metadata(self, audio_path):
        """Try to extract lyrics from audio file metadata"""
        try:
            audio_file = mutagen.File(audio_path)
            if audio_file is not None:
                # Check common lyrics tags
                lyrics_tags = ['LYRICS', 'USLT', 'lyrics', '©lyr']
                for tag in lyrics_tags:
                    if tag in audio_file:
                        return str(audio_file[tag][0])
        except:
            pass
            
        return None
        
    def _check_originality(self, lyrics):
        """Basic originality check based on common patterns"""
        if not lyrics:
            return 0.0
            
        # Simple metrics for originality
        unique_words = len(set(lyrics.lower().split()))
        total_words = len(lyrics.split())
        
        if total_words == 0:
            return 0.0
            
        # Check for repetitive patterns
        repetition_ratio = unique_words / total_words
        
        # Check for RustChain specific content
        rustchain_refs = len(re.findall(r'rust|chain|rtc|mining|cpu|vote|vintage|antiquity', lyrics.lower()))
        relevance_score = min(rustchain_refs / 10.0, 1.0)
        
        return (repetition_ratio * 0.6) + (relevance_score * 0.4)
        
    def save_submission(self, audio_path, lyrics_content, submitter, validation_results):
        """Save validated submission to database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS music_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submitter TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    lyrics TEXT,
                    duration REAL,
                    keywords_found INTEGER,
                    validation_status TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                INSERT INTO music_submissions 
                (submitter, audio_path, lyrics, duration, keywords_found, validation_status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                submitter,
                audio_path,
                lyrics_content,
                validation_results['metadata'].get('duration'),
                validation_results['metadata'].get('keywords_found', 0),
                'valid' if validation_results['valid'] else 'invalid',
                json.dumps(validation_results)
            ))
            
            conn.commit()
            return cursor.lastrowid

def validate_music_bounty(audio_file, lyrics_file=None, submitter="anonymous"):
    """CLI function to validate a music submission"""
    validator = MusicValidator()
    
    results = validator.validate_submission(audio_file, lyrics_file)
    
    print(f"\n=== Music Bounty Validation Results ===")
    print(f"Audio File: {audio_file}")
    print(f"Duration: {results['metadata'].get('duration', 'Unknown')}s")
    print(f"Keywords Found: {results['metadata'].get('keywords_found', 0)}/2 required")
    print(f"Keywords: {', '.join(results['metadata'].get('keyword_matches', []))}")
    
    if results['valid']:
        print("✅ SUBMISSION VALID - Meets bounty requirements!")
    else:
        print("❌ SUBMISSION INVALID")
        
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
            
    if results['warnings']:
        print("\nWarnings:")
        for warning in results['warnings']:
            print(f"  - {warning}")
            
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python music_validator.py <audio_file> [lyrics_file] [submitter]")
        sys.exit(1)
        
    audio_file = sys.argv[1]
    lyrics_file = sys.argv[2] if len(sys.argv) > 2 else None
    submitter = sys.argv[3] if len(sys.argv) > 3 else "anonymous"
    
    validate_music_bounty(audio_file, lyrics_file, submitter)