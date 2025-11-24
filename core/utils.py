import re
import os
from typing import Dict, Optional
import PyPDF2
import docx2txt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import UserProfile


def extract_resume_data(file_path: str) -> Dict[str, Optional[str]]:
    """
    Extract name, email, and phone from PDF or DOCX resume file.

    Args:
        file_path: Path to the resume file

    Returns:
        Dictionary containing extracted data
    """
    text = ""

    if file_path.lower().endswith('.pdf'):
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return {'name': None, 'email': None, 'phone': None}

    elif file_path.lower().endswith('.docx'):
        try:
            text = docx2txt.process(file_path)
        except Exception as e:
            print(f"Error reading DOCX: {e}")
            return {'name': None, 'email': None, 'phone': None}
    else:
        return {'name': None, 'email': None, 'phone': None}

    # Extract information using regex patterns
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})'

    emails = re.findall(email_pattern, text)
    phones = re.findall(phone_pattern, text)

    # Extract name (first line or first name-like pattern)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    name = None
    for line in lines[:5]:  # Check first 5 lines for name
        if len(line.split()) >= 2 and not any(char.isdigit() for char in line):
            name = line.title()
            break

    return {
        'name': name,
        'email': emails[0] if emails else None,
        'phone': ''.join(phones[0]) if phones else None,
    }


def update_profile_from_resume(profile: UserProfile) -> None:
    """
    Update user profile with data extracted from resume.

    Args:
        profile: UserProfile instance
    """
    if not profile.resume:
        return

    file_path = profile.resume.path
    extracted_data = extract_resume_data(file_path)

    # Update profile fields only if they're empty
    if not profile.name and extracted_data['name']:
        profile.name = extracted_data['name']
    if not profile.email and extracted_data['email']:
        profile.email = extracted_data['email']
    if not profile.phone and extracted_data['phone']:
        profile.phone = extracted_data['phone']

    profile.save()