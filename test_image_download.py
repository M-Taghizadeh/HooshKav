import os
import re
from urllib.parse import urljoin
import requests

def download_article_image(url, save_path="downloaded_image.jpg"):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Hooshkav/1.0; +https://github.com/M-Taghizadeh/HooshKav)"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if not resp.ok:
            print(f"Failed to fetch page: {resp.status_code}")
            return False

        html = resp.text
        img_url = None

        # Check og:image or twitter:image
        match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
        if not match:
            match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)

        if match:
            img_url = match.group(1).strip()
        else:
            # Fallback to first img tag
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
            if img_match:
                img_url = img_match.group(1).strip()

        if not img_url:
            print("No image found in page.")
            return False

        if not img_url.startswith("http"):
            img_url = urljoin(url, img_url)

        print(f"Found image URL: {img_url}")

        img_resp = requests.get(img_url, headers=headers, timeout=10)
        if img_resp.ok:
            absolute_save_path = os.path.abspath(save_path)
            with open(absolute_save_path, "wb") as f:
                f.write(img_resp.content)
            print(f"Image successfully saved to {absolute_save_path}")
            return True
        else:
            print(f"Failed to download image file: {img_resp.status_code}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    import sys
    target_url = sys.argv[1] if len(sys.argv) > 1 else input("Enter article URL: ")
    download_article_image(target_url)
