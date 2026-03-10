import requests
from pathlib import Path


# English profanity datasets
EN_SOURCES = [
    "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en",
    "https://raw.githubusercontent.com/areebbeigh/profanityfilter/master/profanityfilter/data/badwords.txt"
]





def download_wordlist(url):

    r = requests.get(url, timeout=20)
    r.raise_for_status()

    words = []

    for line in r.text.splitlines():

        w = line.strip().lower()

        if not w:
            continue

        if w.startswith("#"):
            continue

        words.append(w)

    return words


def generate_list():

    words = set()

    # Download English datasets
    for src in EN_SOURCES:

        try:
            print("Downloading:", src)
            words.update(download_wordlist(src))

        except Exception as e:
            print("Failed:", src, e)

    # Add Hindi / Hinglish
    words.update(HINDI_SLURS)

    return words


def main():

    # project root = moderator-service/service
    root = Path(__file__).resolve().parents[1]

    output_dir = root / "app" / "i18n" / "profanity_lists"

    output_dir.mkdir(parents=True, exist_ok=True)

    words = generate_list()

    output_file = output_dir / "profanity.txt"

    output_file.write_text("\n".join(sorted(words)), encoding="utf-8")

    print("\nSaved file:")
    print(output_file.resolve())

    print("\nTotal words:", len(words))


if __name__ == "__main__":
    main()