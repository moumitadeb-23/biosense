import os
import shutil
import zipfile
from pathlib import Path

def main():
    source_dir = Path(r"C:\Users\mamai\.gemini\antigravity\scratch\biosense")
    scratch_dir = Path(r"C:\Users\mamai\.gemini\antigravity\scratch")
    brain_dir = Path(r"C:\Users\mamai\.gemini\antigravity\brain\e2c2d783-c760-45be-ac7e-53b69edaf148")
    user_downloads_dir = Path(os.environ.get("USERPROFILE", r"C:\Users\mamai")) / "Downloads"

    target_zip_name = "BioSense_Project_Complete.zip"
    primary_zip = scratch_dir / target_zip_name

    exclude_dirs = {".git", "__pycache__", ".pytest_cache"}
    exclude_extensions = {".pyc", ".zip"}


    print(f"[*] Compressing BioSense project from: {source_dir}")
    file_count = 0
    with zipfile.ZipFile(primary_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_extensions:
                    continue
                full_path = Path(root) / file
                # Store relative to biosense parent, so extraction creates a 'biosense/...' root folder
                rel_path = full_path.relative_to(source_dir.parent)
                zf.write(full_path, rel_path)
                file_count += 1

    zip_size_mb = os.path.getsize(primary_zip) / (1024 * 1024)
    print(f"[+] ZIP Archive created successfully: {primary_zip}")
    print(f"[+] Total archived files: {file_count}")
    print(f"[+] Compressed Size: {zip_size_mb:.2f} MB")

    # Copy to Artifacts directory for in-chat access
    brain_zip = brain_dir / target_zip_name
    shutil.copy2(primary_zip, brain_zip)
    print(f"[+] Copied to Brain Artifacts: {brain_zip}")

    # Copy to User's personal Downloads folder for easy file sharing
    if user_downloads_dir.exists():
        download_zip = user_downloads_dir / target_zip_name
        shutil.copy2(primary_zip, download_zip)
        print(f"[+] Copied to User Downloads folder: {download_zip}")

if __name__ == "__main__":
    main()
