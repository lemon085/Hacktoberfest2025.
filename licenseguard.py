#!/usr/bin/env python3
"""
LicenseGuard: AI-Powered Open Source License Compliance Checker
Author: Shakeel Ahmed (GitHub: lemon085)
Usage: python licenseguard.py --repo https://github.com/user/repo --api-key sk-or-v1-...
"""

import os
import re
import json
import argparse
import subprocess
import shutil
from pathlib import Path
import requests

# Known license filenames (case-insensitive)
LICENSE_FILENAMES = {'license', 'licence', 'copying', 'unlicense'}

# Dependency manifest files by ecosystem
MANIFEST_FILES = {
    'npm': 'package.json',
    'python': 'requirements.txt',
    'pipenv': 'Pipfile',
    'poetry': 'pyproject.toml',
    'go': 'go.mod',
    'rust': 'Cargo.toml',
    'maven': 'pom.xml',
    'gradle': 'build.gradle',
    'nuget': 'packages.config'
}

def clone_repo(repo_url: str, clone_dir: Path):
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    print(f"🔍 Cloning {repo_url}...")
    subprocess.run(['git', 'clone', '--depth=1', repo_url, str(clone_dir)], check=True, capture_output=True)

def find_license_file(root: Path):
    for file in root.iterdir():
        if file.is_file() and file.name.lower().split('.')[0] in LICENSE_FILENAMES:
            return file
    return None

def extract_dependencies(root: Path):
    deps = {}
    for ecosystem, filename in MANIFEST_FILES.items():
        manifest = root / filename
        if manifest.exists():
            try:
                if ecosystem == 'npm':
                    data = json.loads(manifest.read_text(encoding='utf-8'))
                    deps_list = list(data.get('dependencies', {}).keys())
                    deps['npm'] = deps_list[:10]  # Limit for token efficiency
                elif ecosystem == 'python':
                    lines = manifest.read_text(encoding='utf-8').splitlines()
                    deps['python'] = [line.split('==')[0].strip() for line in lines if line.strip() and not line.startswith('#')][:10]
                elif ecosystem == 'go':
                    content = manifest.read_text(encoding='utf-8')
                    modules = re.findall(r'^\s*([^\s]+)\s+v\d', content, re.MULTILINE)
                    deps['go'] = modules[:10]
                # Add more as needed
            except Exception as e:
                deps[ecosystem] = f"[Error parsing: {e}]"
    return deps

def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return f"[Unable to read: {e}]"

def generate_llm_prompt(project_license: str, deps: dict, repo_url: str) -> str:
    return f"""You are an expert in open-source licensing and compliance.

Analyze the following project for license risks:

**Repository**: {repo_url}

**Project License**:
{project_license if project_license else "NO LICENSE FOUND — THIS IS A HIGH-RISK ISSUE"}

**Detected Dependencies**:
{json.dumps(deps, indent=2) if deps else "None detected"}

Provide a professional compliance report with:

1. **License Status**: Is the project properly licensed?
2. **Risk Assessment**: 
   - Missing license?
   - Copyleft (e.g., GPL) dependencies in permissively licensed (MIT/Apache) project?
   - Conflicting licenses?
3. **Actionable Recommendations**:
   - What license should be added?
   - Which dependencies need review?
   - Legal best practices

Format your response in Markdown with clear headings and bullet points.
"""

def query_openrouter(prompt: str, api_key: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/lemon085",
        "X-Title": "LicenseGuard",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o-mini",  # Cost-effective for analysis
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1500
    }
    print("🧠 Analyzing license compliance with AI...")
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter error: {response.status_code} - {response.text}")
    return response.json()['choices'][0]['message']['content']

def main():
    parser = argparse.ArgumentParser(description="LicenseGuard: AI License Compliance Checker")
    parser.add_argument("--repo", required=True, help="GitHub repo URL (e.g., https://github.com/user/repo)")
    parser.add_argument("--api-key", required=True, help="OpenRouter API key")
    parser.add_argument("--output", default="LICENSE_REPORT.md", help="Output report file")
    args = parser.parse_args()

    clone_dir = Path("temp_license_scan")
    try:
        clone_repo(args.repo, clone_dir)

        # Step 1: Check for LICENSE
        license_file = find_license_file(clone_dir)
        project_license = read_file_safe(license_file) if license_file else ""

        # Step 2: Extract dependencies
        deps = extract_dependencies(clone_dir)

        # Step 3: Generate AI report
        prompt = generate_llm_prompt(project_license, deps, args.repo)
        report = query_openrouter(prompt, args.api_key)

        # Step 4: Save report
        output_path = Path(args.output)
        output_path.write_text(report, encoding='utf-8')
        print(f"\n✅ License compliance report saved to: {output_path.resolve()}")

        # Bonus: Print quick status
        if not license_file:
            print("\n⚠️  WARNING: No LICENSE file found! This project is not open source by default.")
        else:
            print(f"\n📄 License file found: {license_file.name}")

    finally:
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

if __name__ == "__main__":
    main()
