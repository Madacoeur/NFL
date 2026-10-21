"""
Validateur de paquet .pptx.

Aucun PowerPoint ni LibreOffice n'est disponible dans le sandbox pour ouvrir
le fichier produit. Ce module vérifie donc mécaniquement les invariants du
format OOXML dont le non-respect provoque le message « PowerPoint ne peut pas
ouvrir ce fichier » :

  1. L'archive ZIP est intègre.
  2. Chaque partie XML est bien formée.
  3. Chaque partie XML (hors .rels et manifeste) est déclarée dans
     [Content_Types].xml, directement ou via une extension par défaut.
  4. Chaque relation (`Relationship/@Target`) pointe vers une partie
     réellement présente dans l'archive.
  5. Chaque référence `r:id` utilisée dans un XML possède une relation
     correspondante dans le fichier .rels de cette partie.
  6. Le nombre de diapositives déclarées correspond aux parties présentes.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from xml.dom.minidom import parseString

NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _rels_de(partie: str) -> str:
    """Chemin du fichier .rels associé à une partie."""
    dossier, nom = posixpath.split(partie)
    return posixpath.join(dossier, "_rels", nom + ".rels")


def valider(chemin: str) -> dict:
    """Valide un fichier .pptx. Retourne un rapport avec la liste des erreurs."""
    erreurs: list[str] = []
    avertissements: list[str] = []

    with zipfile.ZipFile(chemin) as z:
        noms = set(z.namelist())

        # --- 1. Intégrité de l'archive --------------------------------
        corrompu = z.testzip()
        if corrompu:
            erreurs.append(f"Entrée ZIP corrompue : {corrompu}")

        # --- 2. XML bien formé ----------------------------------------
        documents = {}
        for nom in sorted(noms):
            if not (nom.endswith(".xml") or nom.endswith(".rels")):
                continue
            contenu = z.read(nom)
            try:
                documents[nom] = parseString(contenu)
            except Exception as exc:
                erreurs.append(f"XML mal formé : {nom} ({exc})")

        # --- 3. Déclarations de types de contenu ----------------------
        if "[Content_Types].xml" not in noms:
            erreurs.append("[Content_Types].xml absent")
        else:
            ct = z.read("[Content_Types].xml").decode("utf-8")
            declarees = set(re.findall(r'PartName="([^"]+)"', ct))
            extensions = set(
                e.lower() for e in re.findall(r'Extension="([^"]+)"', ct)
            )
            for nom in sorted(noms):
                if nom == "[Content_Types].xml":
                    continue
                ext = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
                if "/" + nom in declarees or ext in extensions:
                    continue
                erreurs.append(f"Partie non déclarée dans [Content_Types] : {nom}")

        # --- 4. Cibles des relations ----------------------------------
        for nom, doc in documents.items():
            if not nom.endswith(".rels"):
                continue
            base = posixpath.dirname(posixpath.dirname(nom))  # retire /_rels
            for rel in doc.getElementsByTagName("Relationship"):
                mode = rel.getAttribute("TargetMode")
                if mode == "External":
                    continue
                cible = rel.getAttribute("Target")
                resolu = posixpath.normpath(posixpath.join(base, cible)).lstrip("/")
                if resolu not in noms:
                    erreurs.append(
                        f"Relation cassée dans {nom} : "
                        f"{rel.getAttribute('Id')} -> {cible} (résolu : {resolu})"
                    )

        # --- 5. Références r:id utilisées -----------------------------
        for nom, doc in documents.items():
            if nom.endswith(".rels") or nom == "[Content_Types].xml":
                continue
            contenu = z.read(nom).decode("utf-8")
            utilises = set(re.findall(r'r:(?:id|embed|link)="([^"]+)"', contenu))
            if not utilises:
                continue
            fichier_rels = _rels_de(nom)
            if fichier_rels not in documents:
                erreurs.append(
                    f"{nom} référence {sorted(utilises)} mais {fichier_rels} est absent"
                )
                continue
            definis = {
                rel.getAttribute("Id")
                for rel in documents[fichier_rels].getElementsByTagName("Relationship")
            }
            for rid in sorted(utilises - definis):
                erreurs.append(f"{nom} référence r:id={rid} non défini dans les rels")

        # --- 6. Cohérence du nombre de diapositives -------------------
        parties_slides = {n for n in noms if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)}
        if "ppt/presentation.xml" in documents:
            declarees_slides = documents["ppt/presentation.xml"].getElementsByTagName(
                "p:sldId"
            )
            if len(declarees_slides) != len(parties_slides):
                erreurs.append(
                    f"{len(declarees_slides)} diapositives déclarées dans "
                    f"presentation.xml mais {len(parties_slides)} parties présentes"
                )
            for partie in sorted(parties_slides):
                if _rels_de(partie) not in noms:
                    erreurs.append(f"Fichier .rels manquant pour {partie}")

        # --- Contrôles souples ----------------------------------------
        for attendu in (
            "ppt/presentation.xml",
            "ppt/slideMasters/slideMaster1.xml",
            "ppt/slideLayouts/slideLayout1.xml",
            "ppt/theme/theme1.xml",
            "_rels/.rels",
        ):
            if attendu not in noms:
                erreurs.append(f"Partie obligatoire absente : {attendu}")

        taille_octets = sum(z.getinfo(n).file_size for n in noms)

    return {
        "valide": not erreurs,
        "erreurs": erreurs,
        "avertissements": avertissements,
        "n_parties": len(noms),
        "n_slides": len(parties_slides),
        "taille_decompressee": taille_octets,
    }


def verifier_geometrie(chemin: str) -> dict:
    """Détecte les formes qui sortent du cadre de la diapositive.

    Un débordement ne corrompt pas le fichier — PowerPoint l'ouvrira — mais
    tronque visuellement le contenu. Comme aucun logiciel de rendu n'est
    disponible ici pour contrôler l'aspect, cette vérification géométrique
    remplace l'inspection visuelle.
    """
    debordements: list[dict] = []
    with zipfile.ZipFile(chemin) as z:
        presentation = parseString(z.read("ppt/presentation.xml"))
        taille = presentation.getElementsByTagName("p:sldSz")
        if not taille:
            return {"applicable": False}
        largeur = int(taille[0].getAttribute("cx"))
        hauteur = int(taille[0].getAttribute("cy"))

        parties = sorted(
            (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group()),
        )
        n_formes = 0
        for partie in parties:
            numero = int(re.search(r"(\d+)", partie.rsplit("/", 1)[-1]).group())
            doc = parseString(z.read(partie))
            for xfrm in doc.getElementsByTagName("a:xfrm"):
                # Le groupe racine porte une transformation nulle : on l'ignore.
                if xfrm.parentNode.nodeName == "p:grpSpPr":
                    continue
                offsets = xfrm.getElementsByTagName("a:off")
                extents = xfrm.getElementsByTagName("a:ext")
                if not offsets or not extents:
                    continue
                n_formes += 1
                x = int(offsets[0].getAttribute("x"))
                y = int(offsets[0].getAttribute("y"))
                cx = int(extents[0].getAttribute("cx"))
                cy = int(extents[0].getAttribute("cy"))
                depasse = {
                    "gauche": -x if x < 0 else 0,
                    "haut": -y if y < 0 else 0,
                    "droite": (x + cx) - largeur if x + cx > largeur else 0,
                    "bas": (y + cy) - hauteur if y + cy > hauteur else 0,
                }
                if any(depasse.values()):
                    debordements.append(
                        {"slide": numero, "x": x, "y": y, "cx": cx, "cy": cy,
                         **{k: v for k, v in depasse.items() if v}}
                    )

    return {
        "applicable": True,
        "conforme": not debordements,
        "debordements": debordements,
        "n_formes": n_formes,
        "largeur": largeur,
        "hauteur": hauteur,
    }


def afficher_rapport(chemin: str, journal=print, geometrie: bool = True) -> bool:
    """Valide et affiche un rapport lisible. Retourne True si tout est conforme."""
    r = valider(chemin)
    journal(f"Validation de {chemin}")
    journal(f"  parties : {r['n_parties']} | diapositives : {r['n_slides']}")
    if r["valide"]:
        journal("  [OK] Structure OOXML conforme (6 familles de contrôles).")
    else:
        journal(f"  [ECHEC] {len(r['erreurs'])} erreur(s) de structure :")
        for e in r["erreurs"]:
            journal(f"    - {e}")
    for a in r["avertissements"]:
        journal(f"  [!] {a}")

    conforme_geo = True
    if geometrie:
        g = verifier_geometrie(chemin)
        if g.get("applicable"):
            if g["conforme"]:
                journal(
                    f"  [OK] Géométrie : {g['n_formes']} formes, "
                    "aucune hors cadre."
                )
            else:
                conforme_geo = False
                journal(
                    f"  [ECHEC] {len(g['debordements'])} forme(s) hors cadre :"
                )
                for d in g["debordements"][:10]:
                    cotes = ", ".join(
                        f"{c} +{d[c]}"
                        for c in ("gauche", "haut", "droite", "bas")
                        if c in d
                    )
                    journal(f"    - slide {d['slide']} : dépasse {cotes}")

    return r["valide"] and conforme_geo


if __name__ == "__main__":
    import sys

    cible = sys.argv[1] if len(sys.argv) > 1 else "presentation.pptx"
    raise SystemExit(0 if afficher_rapport(cible) else 1)
