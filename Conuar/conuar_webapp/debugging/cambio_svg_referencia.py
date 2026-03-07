import os

folder = r"C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\media\inspection_photos\STAGING"

for file in os.listdir(folder):
    if file.endswith(".svg"):
        path = os.path.join(folder, file)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace("04-03-26", "04MAR")
        content = content.replace("1443", "A2026")

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

print("SVG updated")