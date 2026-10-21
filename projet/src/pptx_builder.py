"""
Générateur de fichiers PowerPoint (.pptx) en Python pur.

Le sandbox n'a pas d'accès réseau : `python-pptx` est indisponible. Or un
fichier .pptx n'est rien d'autre qu'une archive ZIP contenant des documents
XML au format OOXML (ECMA-376). Ce module écrit directement cette structure
avec `zipfile` et `xml`.

Arborescence produite :

    [Content_Types].xml          déclaration des types MIME
    _rels/.rels                  relation racine -> presentation.xml
    docProps/core.xml            métadonnées (titre, auteur, date)
    docProps/app.xml             métadonnées applicatives
    ppt/presentation.xml         liste des diapositives et format de page
    ppt/_rels/...                relations de la présentation
    ppt/theme/theme1.xml         thème (palette, polices)
    ppt/slideMasters/...         masque
    ppt/slideLayouts/...         disposition vierge
    ppt/slides/slideN.xml        une diapositive par fichier

Unité de mesure : l'EMU (English Metric Unit), 914 400 EMU par pouce.

API :

    pres = Presentation()
    s = pres.ajouter_slide()
    s.rectangle(x, y, largeur, hauteur, couleur="1F4E79")
    s.texte("Bonjour", x, y, largeur, hauteur, taille=32, gras=True)
    pres.enregistrer("sortie.pptx")
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

EMU_PAR_POUCE = 914400
EMU_PAR_CM = 360000

# Format 16:9 standard : 13,333 x 7,5 pouces.
LARGEUR_16_9 = 12192000
HAUTEUR_16_9 = 6858000

ALIGNEMENTS = {"gauche": "l", "centre": "ctr", "droite": "r", "justifie": "just"}
ANCRAGES = {"haut": "t", "milieu": "ctr", "bas": "b"}


def cm(valeur: float) -> int:
    """Convertit des centimètres en EMU."""
    return int(valeur * EMU_PAR_CM)


def pouces(valeur: float) -> int:
    """Convertit des pouces en EMU."""
    return int(valeur * EMU_PAR_POUCE)


# ---------------------------------------------------------------------------
# Fragments de texte
# ---------------------------------------------------------------------------


class Fragment:
    """Portion de texte avec sa propre mise en forme (un « run » OOXML)."""

    def __init__(
        self,
        texte: str,
        taille: float = 18,
        gras: bool = False,
        italique: bool = False,
        couleur: str = "1A1A1A",
        police: str = "Calibri",
        espacement: int | None = None,
    ):
        self.texte = texte
        self.taille = taille
        self.gras = gras
        self.italique = italique
        self.couleur = couleur
        self.police = police
        self.espacement = espacement

    def xml(self) -> str:
        attrs = [f'lang="fr-FR"', f'sz="{int(self.taille * 100)}"', 'dirty="0"']
        attrs.append(f'b="{1 if self.gras else 0}"')
        attrs.append(f'i="{1 if self.italique else 0}"')
        if self.espacement is not None:
            attrs.append(f'spc="{self.espacement}"')
        return (
            f"<a:r><a:rPr {' '.join(attrs)}>"
            f'<a:solidFill><a:srgbClr val="{self.couleur}"/></a:solidFill>'
            f'<a:latin typeface="{escape(self.police)}"/>'
            f'<a:cs typeface="{escape(self.police)}"/>'
            f"</a:rPr><a:t>{escape(self.texte)}</a:t></a:r>"
        )


class Paragraphe:
    """Ligne de texte composée d'un ou plusieurs fragments."""

    def __init__(
        self,
        fragments: list[Fragment] | Fragment | None = None,
        alignement: str = "gauche",
        puce: bool = False,
        niveau: int = 0,
        interligne: float | None = None,
        espace_avant: float = 0,
        espace_apres: float = 0,
    ):
        if fragments is None:
            fragments = []
        elif isinstance(fragments, Fragment):
            fragments = [fragments]
        self.fragments = fragments
        self.alignement = alignement
        self.puce = puce
        self.niveau = niveau
        self.interligne = interligne
        self.espace_avant = espace_avant
        self.espace_apres = espace_apres

    def xml(self) -> str:
        attrs = [f'algn="{ALIGNEMENTS.get(self.alignement, "l")}"']
        if self.niveau:
            attrs.append(f'lvl="{self.niveau}"')
        if self.puce:
            # Retrait et puce ronde.
            attrs.append('marL="285750" indent="-285750"')

        interne = ""
        if self.interligne:
            interne += (
                f'<a:lnSpc><a:spcPct val="{int(self.interligne * 100000)}"/></a:lnSpc>'
            )
        if self.espace_avant:
            interne += (
                f'<a:spcBef><a:spcPts val="{int(self.espace_avant * 100)}"/></a:spcBef>'
            )
        if self.espace_apres:
            interne += (
                f'<a:spcAft><a:spcPts val="{int(self.espace_apres * 100)}"/></a:spcAft>'
            )
        if self.puce:
            interne += '<a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>'
        else:
            interne += "<a:buNone/>"

        ppr = f"<a:pPr {' '.join(attrs)}>{interne}</a:pPr>"
        runs = "".join(f.xml() for f in self.fragments)
        return f"<a:p>{ppr}{runs}</a:p>"


# ---------------------------------------------------------------------------
# Diapositive
# ---------------------------------------------------------------------------


class Slide:
    """Une diapositive : une liste de formes positionnées en EMU."""

    def __init__(self, numero: int):
        self.numero = numero
        self._formes: list[str] = []
        self._id = 1

    def _prochain_id(self) -> int:
        self._id += 1
        return self._id

    # -- Formes géométriques -------------------------------------------

    def rectangle(
        self,
        x: int,
        y: int,
        largeur: int,
        hauteur: int,
        couleur: str | None = "1F4E79",
        bordure: str | None = None,
        epaisseur_bordure: int = 12700,
        transparence: float | None = None,
        arrondi: bool = False,
        forme: str | None = None,
    ) -> None:
        """Ajoute un rectangle (ou autre forme préréglée)."""
        prst = forme or ("roundRect" if arrondi else "rect")
        if couleur:
            if transparence:
                alpha = int((1 - transparence) * 100000)
                remplissage = (
                    f'<a:solidFill><a:srgbClr val="{couleur}">'
                    f'<a:alpha val="{alpha}"/></a:srgbClr></a:solidFill>'
                )
            else:
                remplissage = f'<a:solidFill><a:srgbClr val="{couleur}"/></a:solidFill>'
        else:
            remplissage = "<a:noFill/>"

        if bordure:
            trait = (
                f'<a:ln w="{epaisseur_bordure}">'
                f'<a:solidFill><a:srgbClr val="{bordure}"/></a:solidFill></a:ln>'
            )
        else:
            trait = '<a:ln><a:noFill/></a:ln>'

        ident = self._prochain_id()
        self._formes.append(
            f"<p:sp><p:nvSpPr>"
            f'<p:cNvPr id="{ident}" name="Forme {ident}"/>'
            f"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
            f"<p:spPr><a:xfrm>"
            f'<a:off x="{int(x)}" y="{int(y)}"/>'
            f'<a:ext cx="{max(int(largeur), 1)}" cy="{max(int(hauteur), 1)}"/>'
            f"</a:xfrm>"
            f'<a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>'
            f"{remplissage}{trait}</p:spPr>"
            f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:buNone/></a:pPr></a:p>'
            f"</p:txBody></p:sp>"
        )

    def ligne(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        couleur: str = "CCCCCC",
        epaisseur: int = 12700,
    ) -> None:
        """Ajoute un trait droit entre deux points."""
        ident = self._prochain_id()
        x, y = min(x1, x2), min(y1, y2)
        cx, cy = abs(x2 - x1), abs(y2 - y1)
        retourne_h = ' flipH="1"' if x2 < x1 else ""
        retourne_v = ' flipV="1"' if y2 < y1 else ""
        self._formes.append(
            f"<p:cxnSp><p:nvCxnSpPr>"
            f'<p:cNvPr id="{ident}" name="Trait {ident}"/>'
            f"<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>"
            f'<p:spPr><a:xfrm{retourne_h}{retourne_v}>'
            f'<a:off x="{int(x)}" y="{int(y)}"/>'
            f'<a:ext cx="{max(int(cx), 1)}" cy="{max(int(cy), 1)}"/></a:xfrm>'
            f'<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{epaisseur}">'
            f'<a:solidFill><a:srgbClr val="{couleur}"/></a:solidFill></a:ln>'
            f"</p:spPr></p:cxnSp>"
        )

    # -- Texte ---------------------------------------------------------

    def bloc_texte(
        self,
        paragraphes: list[Paragraphe],
        x: int,
        y: int,
        largeur: int,
        hauteur: int,
        ancrage: str = "haut",
        ajuster: bool = True,
        marge: int = 0,
    ) -> None:
        """Ajoute une zone de texte composée de plusieurs paragraphes."""
        ident = self._prochain_id()
        corps = "".join(p.xml() for p in paragraphes) or Paragraphe().xml()
        autofit = "<a:normAutofit/>" if ajuster else "<a:noAutofit/>"
        self._formes.append(
            f"<p:sp><p:nvSpPr>"
            f'<p:cNvPr id="{ident}" name="Texte {ident}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f"<p:spPr><a:xfrm>"
            f'<a:off x="{int(x)}" y="{int(y)}"/>'
            f'<a:ext cx="{max(int(largeur), 1)}" cy="{max(int(hauteur), 1)}"/>'
            f"</a:xfrm>"
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f"<a:noFill/></p:spPr>"
            f'<p:txBody><a:bodyPr wrap="square" anchor="{ANCRAGES.get(ancrage, "t")}"'
            f' lIns="{marge}" tIns="{marge}" rIns="{marge}" bIns="{marge}">'
            f"{autofit}</a:bodyPr><a:lstStyle/>{corps}</p:txBody></p:sp>"
        )

    def texte(
        self,
        contenu: str,
        x: int,
        y: int,
        largeur: int,
        hauteur: int,
        taille: float = 18,
        gras: bool = False,
        italique: bool = False,
        couleur: str = "1A1A1A",
        police: str = "Calibri",
        alignement: str = "gauche",
        ancrage: str = "haut",
        interligne: float | None = None,
        espacement: int | None = None,
    ) -> None:
        """Raccourci : une zone de texte d'un seul paragraphe."""
        self.bloc_texte(
            [
                Paragraphe(
                    Fragment(
                        contenu,
                        taille=taille,
                        gras=gras,
                        italique=italique,
                        couleur=couleur,
                        police=police,
                        espacement=espacement,
                    ),
                    alignement=alignement,
                    interligne=interligne,
                )
            ],
            x,
            y,
            largeur,
            hauteur,
            ancrage=ancrage,
        )

    # -- Rendu XML -----------------------------------------------------

    def xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            "<p:cSld><p:spTree>"
            "<p:nvGrpSpPr>"
            '<p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            "</p:nvGrpSpPr>"
            "<p:grpSpPr><a:xfrm>"
            '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>'
            "</a:xfrm></p:grpSpPr>"
            f"{''.join(self._formes)}"
            "</p:spTree></p:cSld>"
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
            "</p:sld>"
        )


# ---------------------------------------------------------------------------
# Présentation
# ---------------------------------------------------------------------------


class Presentation:
    """Conteneur de diapositives, sérialisable en .pptx."""

    def __init__(
        self,
        largeur: int = LARGEUR_16_9,
        hauteur: int = HAUTEUR_16_9,
        titre: str = "Présentation",
        auteur: str = "",
    ):
        self.largeur = largeur
        self.hauteur = hauteur
        self.titre = titre
        self.auteur = auteur
        self.slides: list[Slide] = []

    def ajouter_slide(self) -> Slide:
        s = Slide(len(self.slides) + 1)
        self.slides.append(s)
        return s

    # -- Parties statiques du paquet -----------------------------------

    def _content_types(self) -> str:
        overrides = "".join(
            f'<Override PartName="/ppt/slides/slide{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'presentationml.slide+xml"/>'
            for i in range(1, len(self.slides) + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
            'package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/ppt/presentation.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'presentationml.slideMaster+xml"/>'
            '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'presentationml.slideLayout+xml"/>'
            '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.theme+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/'
            'vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            f"{overrides}"
            "</Types>"
        )

    @staticmethod
    def _rels_racine() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" '
            'Target="ppt/presentation.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    def _core(self) -> str:
        maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/'
            '2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"'
            ' xmlns:dcterms="http://purl.org/dc/terms/"'
            ' xmlns:dcmitype="http://purl.org/dc/dcmitype/"'
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{escape(self.titre)}</dc:title>"
            f"<dc:creator>{escape(self.auteur)}</dc:creator>"
            f"<cp:lastModifiedBy>{escape(self.auteur)}</cp:lastModifiedBy>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{maintenant}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{maintenant}'
            "</dcterms:modified>"
            "</cp:coreProperties>"
        )

    def _app(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
            'extended-properties" xmlns:vt="http://schemas.openxmlformats.org/'
            'officeDocument/2006/docPropsVTypes">'
            "<Application>Microsoft Office PowerPoint</Application>"
            f"<Slides>{len(self.slides)}</Slides>"
            "<PresentationFormat>Grand écran</PresentationFormat>"
            "</Properties>"
        )

    def _presentation(self) -> str:
        ids = "".join(
            f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>'
            for i in range(1, len(self.slides) + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/'
            'main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships" xmlns:p="http://schemas.openxmlformats.org/'
            'presentationml/2006/main" saveSubsetFonts="1">'
            '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
            "</p:sldMasterIdLst>"
            f"<p:sldIdLst>{ids}</p:sldIdLst>"
            f'<p:sldSz cx="{self.largeur}" cy="{self.hauteur}"/>'
            f'<p:notesSz cx="{self.hauteur}" cy="{self.largeur}"/>'
            "</p:presentation>"
        )

    def _presentation_rels(self) -> str:
        # rId1 = masque ; rId2..N+1 = diapositives ; puis le thème.
        rels = [
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/slideMaster" '
            'Target="slideMasters/slideMaster1.xml"/>'
        ]
        for i in range(1, len(self.slides) + 1):
            rels.append(
                f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.'
                f'org/officeDocument/2006/relationships/slide" '
                f'Target="slides/slide{i}.xml"/>'
            )
        rels.append(
            f'<Relationship Id="rId{len(self.slides) + 2}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/theme" Target="theme/theme1.xml"/>'
        )
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            f'relationships">{"".join(rels)}</Relationships>'
        )

    @staticmethod
    def _slide_master() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/'
            'main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships" xmlns:p="http://schemas.openxmlformats.org/'
            'presentationml/2006/main">'
            "<p:cSld><p:bg><p:bgPr>"
            '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
            "<a:effectLst/></p:bgPr></p:bg>"
            "<p:spTree>"
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            "</p:nvGrpSpPr>"
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            "</p:spTree></p:cSld>"
            '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1"'
            ' accent2="accent2" accent3="accent3" accent4="accent4"'
            ' accent5="accent5" accent6="accent6" hlink="hlink"'
            ' folHlink="folHlink"/>'
            '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
            "</p:sldLayoutIdLst>"
            "</p:sldMaster>"
        )

    @staticmethod
    def _slide_master_rels() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _slide_layout() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/'
            'main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships" xmlns:p="http://schemas.openxmlformats.org/'
            'presentationml/2006/main" type="blank" preserve="1">'
            "<p:cSld name=\"Vide\"><p:spTree>"
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            "</p:nvGrpSpPr>"
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            "</p:spTree></p:cSld>"
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
            "</p:sldLayout>"
        )

    @staticmethod
    def _slide_layout_rels() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/slideMaster" '
            'Target="../slideMasters/slideMaster1.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _theme() -> str:
        """Thème minimal mais conforme : palette, polices, styles de formes."""

        def police(latin: str) -> str:
            return (
                f'<a:latin typeface="{latin}"/><a:ea typeface=""/>'
                '<a:cs typeface=""/>'
            )

        couleurs = [
            ("dk1", "sysClr", 'val="windowText" lastClr="000000"'),
            ("lt1", "sysClr", 'val="window" lastClr="FFFFFF"'),
            ("dk2", "srgbClr", 'val="0B1F33"'),
            ("lt2", "srgbClr", 'val="F2F5F8"'),
            ("accent1", "srgbClr", 'val="1B5E8C"'),
            ("accent2", "srgbClr", 'val="D64550"'),
            ("accent3", "srgbClr", 'val="E8A33D"'),
            ("accent4", "srgbClr", 'val="2E9E8F"'),
            ("accent5", "srgbClr", 'val="7D5BA6"'),
            ("accent6", "srgbClr", 'val="98A2AD"'),
            ("hlink", "srgbClr", 'val="1B5E8C"'),
            ("folHlink", "srgbClr", 'val="7D5BA6"'),
        ]
        palette = "".join(
            f"<a:{nom}><a:{typ} {attr}/></a:{nom}>" for nom, typ, attr in couleurs
        )

        remplissage_style = (
            "<a:fillStyleLst>"
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '<a:solidFill><a:schemeClr val="phClr"><a:tint val="60000"/>'
            "</a:schemeClr></a:solidFill>"
            '<a:solidFill><a:schemeClr val="phClr"><a:shade val="80000"/>'
            "</a:schemeClr></a:solidFill>"
            "</a:fillStyleLst>"
        )
        trait_style = (
            "<a:lnStyleLst>"
            '<a:ln w="6350" cap="flat" cmpd="sng" algn="ctr">'
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '<a:prstDash val="solid"/></a:ln>'
            '<a:ln w="12700" cap="flat" cmpd="sng" algn="ctr">'
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '<a:prstDash val="solid"/></a:ln>'
            '<a:ln w="19050" cap="flat" cmpd="sng" algn="ctr">'
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '<a:prstDash val="solid"/></a:ln>'
            "</a:lnStyleLst>"
        )
        effet_style = (
            "<a:effectStyleLst>"
            "<a:effectStyle><a:effectLst/></a:effectStyle>"
            "<a:effectStyle><a:effectLst/></a:effectStyle>"
            "<a:effectStyle><a:effectLst/></a:effectStyle>"
            "</a:effectStyleLst>"
        )
        fond_style = (
            "<a:bgFillStyleLst>"
            '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
            '<a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/>'
            "</a:schemeClr></a:solidFill>"
            '<a:solidFill><a:schemeClr val="phClr"><a:shade val="90000"/>'
            "</a:schemeClr></a:solidFill>"
            "</a:bgFillStyleLst>"
        )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            ' name="Analyse NFL">'
            "<a:themeElements>"
            f'<a:clrScheme name="Analyse NFL">{palette}</a:clrScheme>'
            '<a:fontScheme name="Analyse NFL">'
            f"<a:majorFont>{police('Calibri Light')}</a:majorFont>"
            f"<a:minorFont>{police('Calibri')}</a:minorFont>"
            "</a:fontScheme>"
            '<a:fmtScheme name="Analyse NFL">'
            f"{remplissage_style}{trait_style}{effet_style}{fond_style}"
            "</a:fmtScheme>"
            "</a:themeElements>"
            "</a:theme>"
        )

    # -- Écriture ------------------------------------------------------

    def enregistrer(self, chemin: str) -> str:
        """Sérialise la présentation dans un fichier .pptx."""
        if not self.slides:
            raise ValueError("Aucune diapositive à enregistrer.")

        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", self._content_types())
            z.writestr("_rels/.rels", self._rels_racine())
            z.writestr("docProps/core.xml", self._core())
            z.writestr("docProps/app.xml", self._app())
            z.writestr("ppt/presentation.xml", self._presentation())
            z.writestr("ppt/_rels/presentation.xml.rels", self._presentation_rels())
            z.writestr("ppt/theme/theme1.xml", self._theme())
            z.writestr("ppt/slideMasters/slideMaster1.xml", self._slide_master())
            z.writestr(
                "ppt/slideMasters/_rels/slideMaster1.xml.rels",
                self._slide_master_rels(),
            )
            z.writestr("ppt/slideLayouts/slideLayout1.xml", self._slide_layout())
            z.writestr(
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
                self._slide_layout_rels(),
            )
            for i, slide in enumerate(self.slides, 1):
                z.writestr(f"ppt/slides/slide{i}.xml", slide.xml())
                z.writestr(
                    f"ppt/slides/_rels/slide{i}.xml.rels",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
                    '2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/slideLayout" '
                    'Target="../slideLayouts/slideLayout1.xml"/>'
                    "</Relationships>",
                )
        return chemin
