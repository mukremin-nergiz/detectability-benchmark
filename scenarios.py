"""Detectability benchmark: survey-planning scenarios and their reference answers.

Every scenario is a common survey situation taken from a published case study or survey guidance (``sources``).
Values the source does not give are listed in ``assumptions``; nothing else is invented. ``question`` is the
natural-language prompt a model receives; ``target`` and ``survey`` are the Detectability inputs that produce the
reference answer in ``reference``.

    pip install "detectability==0.3.0"
    python scenarios.py            # writes data/scenarios.json and data/reference.csv
    python scenarios.py --check    # recomputes and compares with the stored files (used in CI)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATE = "2026-07-01"
METHODS = ("gravity", "magnetic", "gradient")
STEEL = 3.0  # apparent susceptibility of a highly permeable sphere: M = 3*chi/(3+chi)*H -> 3H as chi -> infinity
STEEL_CYL = 2.0  # same limit for a long cylinder in a transverse field: 2*chi/(2+chi) -> 2

LOC = {
    "Sivas, Türkiye": (39.75, 37.02), "Karapınar, Konya, Türkiye": (37.72, 33.55),
    "Çumra, Konya, Türkiye": (37.57, 32.77), "Trieste Karst, Italy": (45.65, 13.78), "Muan, South Korea": (34.99, 126.48),
    "Peninsular Malaysia": (3.14, 101.69), "Sorbas, Almería, Spain": (37.09, -2.12), "New Jersey, USA": (40.90, -74.60),
    "Shrewsbury, UK": (52.71, -2.75), "Gangwon, South Korea": (37.20, 128.90), "Upper Silesia, Poland": (50.30, 19.00),
    "Attica, Greece": (37.98, 23.73), "Cambridgeshire, UK": (52.20, 0.12), "Liverpool, UK": (53.40, -2.96),
    "Tehran, Iran": (35.69, 51.39), "London, UK": (51.50, -0.12), "Newgrange, Ireland": (53.69, -6.48),
    "Pukanec, Slovakia": (48.35, 18.73), "Saqqara, Egypt": (29.87, 31.22), "Valencia region, Spain": (39.85, -0.48),
    "Nevşehir, Türkiye": (38.62, 34.71), "Heldburg, Germany": (50.28, 10.73), "County Antrim, UK": (54.85, -6.25),
    "Borborema Province, Brazil": (-6.50, -36.50), "Osmaniye, Türkiye": (37.15, 36.35), "Divriği, Sivas, Türkiye": (39.37, 38.11),
    "Denizli, Türkiye": (37.78, 29.09), "Ottawa, Canada": (45.38, -75.70), "Kansas, USA": (39.10, -95.50),
    "Central Italy": (41.90, 12.50), "Illinois, USA": (40.00, -89.00), "Northern England, UK": (53.80, -1.55),
    "Latvia": (56.90, 24.10), "North Sea (German sector)": (54.00, 7.00), "Central Spain": (40.40, -3.70),
    "Central Germany": (51.00, 10.00), "Eskişehir, Türkiye": (39.78, 30.52),
}


def S(id_, tr, en, place, setting, target, sources, assumptions=(), survey=None):
    lat, lon = LOC[place]
    sv = {"latitude": lat, "longitude": lon, "date": DATE, **(survey or {})}
    return {"id": id_, "title_tr": tr, "title": en, "place": place, "setting": setting, "target": target,
            "survey": sv, "sources": list(sources), "assumptions": list(assumptions)}


SCENARIOS = [
    # ---- Karst and sinkholes -------------------------------------------------------------------------------------
    S("K01", "Sivas jipsinde hava dolu erime boşluğu", "Air-filled dissolution cavity in gypsum", "Sivas, Türkiye",
      "Building plot on Sivas gypsum; GPR shows fractures and dissolution spaces in the top 5 m.",
      {"shape": "sphere", "depth_top": 5, "size": 4, "material": "air", "host": "gypsum"},
      ["https://acikerisim.gumushane.edu.tr/xmlui/handle/20.500.12440/2936",
       "https://research.itu.edu.tr/en/publications/sinkhole-development-in-the-sivas-gypsum-karst-turkey/"],
      ["Cavity size (4 m) chosen at the scale of the dissolution spaces described; not a measured value."]),
    S("K02", "Aynı boşluk, su dolu", "Same gypsum cavity, water-filled", "Sivas, Türkiye",
      "As K01, but the void lies below the water table and is water-filled.",
      {"shape": "sphere", "depth_top": 5, "size": 4, "material": "water", "host": "gypsum"},
      ["https://acikerisim.gumushane.edu.tr/xmlui/handle/20.500.12440/2936",
       "https://journal.geo.sav.sk/cgg/article/download/20/16"],
      ["Cavity size as K01."]),
    S("K03", "Sivas jipsinde killi dolgulu boşluk", "Clay-filled dissolution pocket in gypsum", "Sivas, Türkiye",
      "Gypsum karst depression; dissolution zones are often filled with alluvial clay.",
      {"shape": "sphere", "depth_top": 8, "size": 6, "material": "clay", "host": "gypsum"},
      ["https://research.itu.edu.tr/en/publications/sinkhole-development-in-the-sivas-gypsum-karst-turkey/"],
      ["Depth and size chosen at the scale of the cover-subsidence features described; not measured values."]),
    S("K04", "Karapınar'da 40 m derinde örtülü boşluk", "Covered cavity at 40 m below the Konya plain",
      "Karapınar, Konya, Türkiye",
      "Sinkhole (obruk) field; resistivity anomalies interpreted as covered cavities from about 40 m depth.",
      {"shape": "sphere", "depth_top": 40, "size": 15, "material": "air", "host": "limestone"},
      ["https://gcris.ktun.edu.tr/entities/publication/caf53b64-5874-49a0-bf02-812361462be3",
       "https://gcris.ktun.edu.tr/bitstream/20.500.13091/5679/1/B%c4%b0L%c4%b0MSEL-K%c4%b0TAP1.pdf"],
      ["Cavity diameter (15 m) assumed; the 40 m depth is the reported top of the resistivity anomalies."]),
    S("K05", "Karapınar'da oluşmakta olan obruk altı boşluk", "Void below a forming sinkhole", "Karapınar, Konya, Türkiye",
      "Forming sinkhole with 8-10 m deep fissures; nearby sinkholes up to 10 m across and 8 m deep.",
      {"shape": "sphere", "depth_top": 10, "size": 10, "material": "air", "host": "limestone"},
      ["https://gcris.ktun.edu.tr/bitstream/20.500.13091/5679/1/B%c4%b0L%c4%b0MSEL-K%c4%b0TAP1.pdf"],
      ["Void taken below the fissure depth, at the reported sinkhole size."]),
    S("K06", "Çumra'da çökme çanağı altında gevşemiş zemin", "Loosened soil below a sagging depression",
      "Çumra, Konya, Türkiye", "Sagging depressions a few metres deep and about 30 m across on the Konya plain.",
      {"shape": "prism", "depth_top": 2, "depth_bottom": 6, "size": 30, "length": 30, "material": "soil", "host": "clay"},
      ["https://gcris.ktun.edu.tr/bitstream/20.500.13091/5680/1/B%c4%b0L%c4%b0MSEL-K%c4%b0TAP2.pdf"],
      ["Loosened zone modelled as soil (table value) within clay; thickness 4 m assumed."]),
    S("K07", "Trieste karstında kireçtaşı mağarası", "Limestone cave in classical karst", "Trieste Karst, Italy",
      "Microgravity search for caves in karst limestone.",
      {"shape": "sphere", "depth_top": 10, "size": 5, "material": "air", "host": "limestone"},
      ["https://ricerca.ogs.it/retrieve/249d9cac-b09d-4313-b85d-56a4b5011db4/204-207.pdf"],
      ["Cave size and depth assumed at a typical scale for the study area."]),
    S("K08", "Muan'da birbirine bağlı karst boşlukları", "Connected cavity network in karst limestone",
      "Muan, South Korea", "Cavities dissolved, enlarged and connected; surveyed on a 5 m grid and drilled.",
      {"shape": "horizontal_cylinder", "depth_top": 8, "size": 3, "material": "air", "host": "limestone"},
      ["https://koreascience.kr/article/JAKO200722034015598.pub"],
      ["Network modelled as one cylindrical passage 3 m across at 8 m; not reported values."]),
    S("K09", "Temel sahasında sedimanla dolu boşluk", "Sediment-filled cavity below a foundation site",
      "Peninsular Malaysia", "Microgravity and boreholes on limestone bedrock; modelled cavity about 7 m thick and 15 m wide.",
      {"shape": "prism", "depth_top": 5, "depth_bottom": 12, "size": 15, "length": 15, "material": "clay", "host": "limestone"},
      ["https://ukm.my/jsm/pdf_files/SM-PDF-54-6-2025/3.pdf"],
      ["Depth to top (5 m) assumed; fill taken as clay."]),
    S("K10", "Sorbas jipsinde mağara galerisi", "Cave passage in gypsum", "Sorbas, Almería, Spain",
      "Gypsum caves; microgravity struggles because the cave-gypsum density contrast is low.",
      {"shape": "horizontal_cylinder", "depth_top": 6, "size": 3, "material": "air", "host": "gypsum"},
      ["https://doi.org/10.1016/j.enggeo.2015.04.011"],
      ["Passage size and depth assumed at typical values for the cave system."]),
    S("K11", "Sivas'ta dolgulu çökme dolini", "Infilled collapse doline in gypsum", "Sivas, Türkiye",
      "Collapse dolines 50-220 m across in Miocene gypsum SW of Sivas; old dolines are infilled.",
      {"shape": "vertical_cylinder", "depth_top": 2, "depth_bottom": 40, "size": 100, "material": "clay", "host": "gypsum"},
      ["https://springerlink.bibliotecabuap.elogim.com/content/pdf/10.1007/s002540050125.pdf"],
      ["Fill depth (40 m) and clay fill assumed; diameter within the reported range."]),
    # ---- Mine workings ---------------------------------------------------------------------------------------------
    S("M01", "Eski demir madeni açık kuyusu", "Open shaft of an old iron mine", "New Jersey, USA",
      "Empty vertical shaft more than 60 ft deep, about 12 x 8-10 ft; a 0.03 mGal low was recorded.",
      {"shape": "vertical_cylinder", "depth_top": 1, "depth_bottom": 18, "size": 3.2, "material": "air", "host": "granite"},
      ["https://www.osti.gov/biblio/6237347"],
      ["Gneissic host approximated by granite; shaft collar 1 m below ground."]),
    S("M02", "Örtü altında bakır madeni kuyusu", "Copper-mine shaft under 3 m of sediment", "New Jersey, USA",
      "Shafts under about 3 m of unconsolidated sediment; lows of 0.02-0.05 mGal, confirmed by drilling.",
      {"shape": "vertical_cylinder", "depth_top": 3, "depth_bottom": 30, "size": 3, "material": "air", "host": "sandstone"},
      ["https://www.osti.gov/biblio/6237347"],
      ["Shaft depth (30 m) and diameter (3 m) assumed; host taken as sandstone."]),
    S("M03", "Kısmen dolu kömür madeni kuyusu", "Partially filled coal-mine shaft", "Shrewsbury, UK",
      "Microgravity proved best for locating a partially filled coal-mine shaft.",
      {"shape": "vertical_cylinder", "depth_top": 4, "depth_bottom": 40, "size": 3, "material": "gravel", "host": "sandstone"},
      ["https://eprints.keele.ac.uk/154/"],
      ["Loose fill modelled as gravel; dimensions assumed."]),
    S("M04", "Kapatılıp gömülmüş maden kuyusu", "Capped and buried mine shaft", "New Jersey, USA",
      "Old shafts are often capped and buried under later fill; same shaft as M01 with its top at 8 m.",
      {"shape": "vertical_cylinder", "depth_top": 8, "depth_bottom": 30, "size": 3.2, "material": "air", "host": "granite"},
      ["https://www.osti.gov/biblio/6237347",
       "https://www.fhwa.dot.gov/engineering/Geotech/hazards/mine/workshops/ktwkshp/ky0316.pdf"],
      ["Burial depth (8 m) assumed."]),
    S("M05", "Terk edilmiş maden galerisi", "Abandoned mine gallery", "Gangwon, South Korea",
      "Microgravity lines 80 m long, station spacing 1-5 m, over abandoned workings.",
      {"shape": "horizontal_cylinder", "depth_top": 10, "size": 2.5, "material": "air", "host": "granite"},
      ["https://ui.adsabs.harvard.edu/abs/2010AGUFMNS23A1439R"],
      ["Gallery size, depth and host assumed."]),
    S("M06", "Derin kömür galerisi", "Deep coal gallery", "Upper Silesia, Poland",
      "Anthropogenic voids from old coal workings.",
      {"shape": "horizontal_cylinder", "depth_top": 25, "size": 3, "material": "air", "host": "shale"},
      ["https://repo.agh.edu.pl/items/5f7b9158-a4e0-44e8-8ec9-b0dc0a9c2261/full"],
      ["Gallery size and depth assumed."]),
    # ---- Tunnels --------------------------------------------------------------------------------------------------
    S("T01", "Bilinen test tüneli (3 m x 2 m)", "Known test tunnel, 3 m wide and 2 m high", "Attica, Greece",
      "Tunnel 2 m high and 3 m wide, top 2-2.5 m deep, known from a surface hatch.",
      {"shape": "prism", "depth_top": 2.25, "depth_bottom": 4.25, "size": 3, "length": 40, "material": "air", "host": "limestone"},
      ["https://www.balkangeophysoc.gr/online-journal/2012_V15/No_1_March/JBGS_Vol_15_No1_March_2012_p07-18_Orfanos.pdf"],
      ["Host rock taken as limestone; tunnel length across the profile 40 m."]),
    S("T02", "12 m derinde 2 m genişlikte tünel", "Air-filled tunnel, 2 m wide, about 12 m deep", "Cambridgeshire, UK",
      "Field trial over a known tunnel; expected anomaly 14 µGal.",
      {"shape": "horizontal_cylinder", "depth_top": 11, "size": 2, "material": "air", "host": "sandstone"},
      ["https://smggravity.com/posts/detecting-subsurface-tunnels-using-gravity"],
      ["Vendor case study; host rock assumed; tunnel centre at 12 m."]),
    S("T03", "Liverpool'da tarihî tünel", "Historic tunnel in sandstone", "Liverpool, UK",
      "150-year-old tunnel system mapped with microgravity after a desk study.",
      {"shape": "horizontal_cylinder", "depth_top": 4, "size": 3.5, "material": "air", "host": "sandstone"},
      ["https://keele.academia.edu/PStyles"], ["Tunnel size and depth assumed."]),
    S("T04", "Alüvyonda kanat tipi su tüneli", "Qanat-type water tunnel in alluvium", "Tehran, Iran",
      "Microgravity profiles over water tunnels in alluvial gravel.",
      {"shape": "horizontal_cylinder", "depth_top": 8, "size": 1.5, "material": "air", "host": "gravel"},
      ["https://www.earthdoc.org/content/papers/10.3997/2352-8265.20140049"], ["Tunnel size and depth assumed."]),
    S("T05", "Sert kilde kaplamalı tünel", "Lined tunnel in stiff clay", "London, UK",
      "Gravity modelling of a lined tunnel in stiff clay; ignoring the lining gave a 20 % depth error.",
      {"shape": "horizontal_cylinder", "depth_top": 15, "size": 6, "material": "air", "host": "clay"},
      ["https://www.earthdoc.org/content/journals/10.3997/1873-0604.2013032"],
      ["Lining not modelled; size and depth assumed."]),
    # ---- Archaeology (gravity) -------------------------------------------------------------------------------------
    S("A01", "Tümülüs içindeki mezar odası", "Burial chamber inside a mound", "Newgrange, Ireland",
      "Passage tomb; main chamber about 6 m across and 6 m high within the mound.",
      {"shape": "sphere", "depth_top": 6, "size": 6, "material": "air", "host": "soil"},
      ["https://eprints.dkit.ie/300/"], ["Mound fill taken as soil; chamber depth below the station assumed."]),
    S("A02", "Kilise altında kripta", "Crypt below a church floor", "Pukanec, Slovakia",
      "Microgravity inside a church to locate crypts and cellars.",
      {"shape": "prism", "depth_top": 1, "depth_bottom": 3.5, "size": 4, "length": 6, "material": "air", "host": "clay"},
      ["https://journal.geo.sav.sk/cgg/article/view/20"], ["Crypt size and host assumed."]),
    S("A03", "Tabut nişleri", "Coffin niches", "Pukanec, Slovakia",
      "Coffin niches proved too small for reliable microgravity detection.",
      {"shape": "prism", "depth_top": 0.5, "depth_bottom": 1.3, "size": 0.8, "length": 2, "material": "air", "host": "clay"},
      ["https://doaj.org/article/3ceea7651a2e42508cae8e3fad3ad2f5"], ["Niche size assumed."]),
    S("A04", "Kireçtaşında oyma mezar odası", "Rock-cut burial chamber in limestone", "Saqqara, Egypt",
      "Microgravity over an animal cemetery; residual low interpreted as a void.",
      {"shape": "prism", "depth_top": 6, "depth_bottom": 9, "size": 5, "length": 5, "material": "air", "host": "limestone"},
      ["https://nriag.journals.ekb.eg/article_452862.html"], ["Chamber size and depth assumed."]),
    S("A05", "Manastır avlusu altında boş sarnıç", "Empty cistern below a cloister", "Valencia region, Spain",
      "Rainwater cistern: ceiling about 1 m and floor about 4 m below the pavement, capacity 288 m³.",
      {"shape": "prism", "depth_top": 1, "depth_bottom": 4, "size": 9.6, "length": 10, "material": "air", "host": "clay"},
      ["https://www.riarte.es/handle/20.500.12251/5608"], ["Plan dimensions from the volume; host taken as clay."]),
    S("A06", "Aynı sarnıç, su dolu", "Same cistern, water-filled", "Valencia region, Spain",
      "As A05 but full of water.",
      {"shape": "prism", "depth_top": 1, "depth_bottom": 4, "size": 9.6, "length": 10, "material": "water", "host": "clay"},
      ["https://www.riarte.es/handle/20.500.12251/5608"], ["As A05."]),
    S("A07", "Tüfte yeraltı yerleşimi odası", "Underground-settlement room in tuff", "Nevşehir, Türkiye",
      "Resistivity anomalies at 8-20 m interpreted as a systematic void structure around Nevşehir Castle.",
      {"shape": "prism", "depth_top": 10, "depth_bottom": 13, "size": 5, "length": 5, "material": "air", "host": "soil",
       "density_contrast": -1700},
      ["https://avesis.comu.edu.tr/yayin/c4208c7f-16bb-4ea5-837b-f9eecffa626e/preliminary-investigation-of-underground-settlements-of-nevsehir-castle-region-using-2-5-d-electrical-resistivity-tomography-cappadocia-turkey"],
      ["Tuff density about 1.7 g/cm³ assumed (density_contrast -1700); room size assumed."]),
    # ---- Geology and ore ---------------------------------------------------------------------------------------------
    S("G01", "Örtü altında bazalt daykı", "Weathered basalt dyke under cover", "Heldburg, Germany",
      "Ground magnetic profiles across a buried basalt dyke; strike, width and burial depth delineated.",
      {"shape": "dyke", "depth_top": 1, "depth_bottom": 200, "size": 5, "material": "basalt", "host": "sandstone"},
      ["https://www.frontiersin.org/articles/10.3389/feart.2020.592986/full"], ["Dyke width (5 m) assumed."]),
    S("G02", "Tebeşir içinde bazalt daykı", "Basalt dyke cutting chalk", "County Antrim, UK",
      "Dykes associated with the Antrim basalts generally give anomalies below 500 nT.",
      {"shape": "dyke", "depth_top": 2, "depth_bottom": 200, "size": 3, "material": "basalt", "host": "limestone"},
      ["https://mural.maynoothuniversity.ie/8855/1/PG_tertiary%20basalts%201993.pdf"], ["Chalk taken as limestone."]),
    S("G03", "Bazalt lavları içinde bazalt daykı", "Basalt dyke within basalt lavas", "County Antrim, UK",
      "A dyke of normal width (2-3 m) is not normally detected by profiling across the basalts.",
      {"shape": "dyke", "depth_top": 1, "depth_bottom": 200, "size": 2.5, "material": "basalt", "host": "basalt"},
      ["https://mural.maynoothuniversity.ie/8855/1/PG_tertiary%20basalts%201993.pdf"],
      ["Same table properties for dyke and host: no contrast in the model."]),
    S("G04", "Kimberlit borusu", "Kimberlite pipe", "Borborema Province, Brazil",
      "Pipe about 200 m across resolved by ground gravity; magnetically distinct from its host.",
      {"shape": "vertical_cylinder", "depth_top": 20, "depth_bottom": 600, "size": 200, "material": "peridotite",
       "host": "granite"},
      ["https://rigeo.sgb.gov.br/bitstream/doc/16586/1/NT_2-Kimberlite_Borborema.pdf"],
      ["Kimberlite approximated by peridotite (no density in the tables, so gravity is not assessed); host granite."]),
    S("G05", "Ofiyolitte podiform kromit merceği", "Podiform chromite pod in ophiolite", "Osmaniye, Türkiye",
      "Microgravity chromite exploration on the Fenk plateau (CG-5).",
      {"shape": "sphere", "depth_top": 15, "size": 10, "material": "peridotite", "host": "peridotite",
       "density_contrast": 1500},
      ["https://opac.geologie.ac.at/ais312/dokumente/EGU/EGU2015-9329.pdf", "https://pubs.usgs.gov/of/1981/0964/report.pdf"],
      ["Density contrast +1500 kg/m³ assumed (chromite about 4.3 vs serpentinised peridotite about 2.8); no magnetic contrast."]),
    S("G07", "Serpantinit içinde manyetit cevheri", "Magnetite ore body in serpentinite", "Divriği, Sivas, Türkiye",
      "Magnetite-bearing ore within serpentinite; distinct gravity and magnetic anomalies over the Dumluca field.",
      {"shape": "prism", "depth_top": 30, "depth_bottom": 150, "size": 60, "length": 100, "material": "peridotite",
       "host": "peridotite", "density_contrast": 1500, "susceptibility_contrast": 1.0},
      ["https://tezara.org/theses/83188", "https://journals.tubitak.gov.tr/earth/vol30/iss1/5"],
      ["Ore geometry, density contrast (+1500 kg/m³) and susceptibility contrast (1.0 SI) assumed."]),
    S("G08", "Denizli havzasını sınırlayan fay", "Basin-bounding fault, sediment against marble", "Denizli, Türkiye",
      "Gravity lineaments interpreted as buried faults at the basin edge.",
      {"shape": "contact", "depth_top": 50, "depth_bottom": 600, "material": "clay", "host": "marble"},
      ["https://www.bohrium.com/paper-details/structural-interpretation-of-sw-part-of-denizli-turkey-based-on-gravity-data-analysis/812649468271788033-347"],
      ["Sediment taken as clay, basement as marble; depths assumed."]),
    S("G09", "Alüvyon altında küçük atımlı fay", "Small-throw buried fault under alluvium", "Eskişehir, Türkiye",
      "Microgravity profiling delineated faults in a buried bedrock valley.",
      {"shape": "contact", "depth_top": 20, "depth_bottom": 40, "material": "clay", "host": "limestone"},
      ["https://agris.fao.org/search/en/records/65dee3277c7033e84bec36ea"],
      ["Throw (20 m) and depths assumed."]),
    S("G10", "Sivas havzasında tuz diyapiri", "Salt diapir in the Sivas Basin", "Sivas, Türkiye",
      "Salt-controlled minibasins and diapirs of the central Sivas Basin.",
      {"shape": "vertical_cylinder", "depth_top": 300, "depth_bottom": 3000, "size": 1500, "material": "rock salt",
       "host": "sandstone"},
      ["https://avesis.cumhuriyet.edu.tr/yayin/81f38789-156c-4055-8ad2-f2d6ec007f1e/minibasins-and-salt-canopy-in-foreland-fold-and-thrust-belts-the-central-sivas-basin-turkey"],
      ["Diapir geometry assumed; host clastics taken as sandstone."]),
    S("G11", "Gömülü ana kaya vadisi (sığ)", "Shallow buried bedrock valley", "Ottawa, Canada",
      "Microgravity lows up to 0.05 mGal over valleys 5-15 m deep; overburden-limestone contrast about 0.3 g/cm³.",
      {"shape": "prism", "depth_top": 1, "depth_bottom": 15, "size": 60, "length": 300, "material": "clay", "host": "limestone",
       "density_contrast": -300},
      ["https://agris.fao.org/search/en/records/65dee3277c7033e84bec36ea"], ["Valley width (60 m) assumed."]),
    S("G12", "Gömülü vadi (geniş)", "Wide buried valley", "Kansas, USA",
      "With 0.01 mGal sensitivity and a 0.3 g/cm³ contrast, valleys deeper than 45 ft can be identified.",
      {"shape": "prism", "depth_top": 2, "depth_bottom": 20, "size": 300, "length": 1000, "material": "clay", "host": "shale",
       "density_contrast": -300},
      ["https://www.kgs.ku.edu/Publications/OFR/1982/KGSOFR1982-17.pdf"], ["Valley width (300 m) assumed."]),
    S("G13", "Kil dolgulu gömülü vadi (zayıf kontrast)", "Buried valley with dense till fill", "Illinois, USA",
      "Small density contrast between shale bedrock and glacial fill; small but measurable low.",
      {"shape": "prism", "depth_top": 5, "depth_bottom": 60, "size": 1000, "length": 5000, "material": "clay", "host": "shale",
       "density_contrast": -100},
      ["https://gsa.confex.com/gsa/2004NC/webprogram/Paper71576.html"],
      ["Contrast (-100 kg/m³) and geometry assumed to represent the 'small contrast' described."]),
    # ---- Ferrous objects and UXO -------------------------------------------------------------------------------------
    S("F01", "1 m derinde tek çelik varil", "Single steel drum at 1 m", "Central Italy",
      "Test site with buried steel drums; total-field anomaly about 290 nT.",
      {"shape": "sphere", "depth_top": 0.7, "size": 0.7, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://arxiv.org/pdf/1009.5555"],
      ["Drum as a sphere of equal volume (0.7 m) with apparent susceptibility 3 (permeable-sphere limit); remanence ignored."]),
    S("F02", "3 m derinde tek çelik varil", "Single steel drum at 3 m", "Illinois, USA",
      "Reported magnetic detection limit for a single drum: 6-11 ft below the surface.",
      {"shape": "sphere", "depth_top": 3, "size": 0.7, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.geometrics.com/wp-content/uploads/2018/10/M-TR34.pdf"], ["As F01."]),
    S("F03", "Gömülü çelik yakıt tankı", "Buried steel underground storage tank", "Illinois, USA",
      "Profile over a single underground storage tank gave a 1000-gamma anomaly.",
      {"shape": "sphere", "depth_top": 1, "size": 2.7, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.geometrics.com/wp-content/uploads/2018/10/M-TR1.pdf"],
      ["10 m³ tank as a sphere of equal volume (2.7 m), apparent susceptibility 3; depth to top 1 m assumed."]),
    S("F04", "Çelik doğalgaz boru hattı", "Steel gas pipeline", "Northern England, UK",
      "Stand-off magnetometry for buried pipelines.",
      {"shape": "horizontal_cylinder", "depth_top": 1.5, "size": 0.6, "material": "air", "host": "soil",
       "susceptibility_contrast": STEEL_CYL},
      ["https://results2021.ref.ac.uk/impact/ea24f6bd-cc50-461c-9191-41803f67c5a9/pdf"],
      ["Pipe as a solid permeable cylinder, apparent susceptibility 2 (transverse limit); diameter and cover assumed."]),
    S("F05", "1,8 m derinde 250 kg uçak bombası (drone)", "250 kg aerial bomb at 1.8 m, drone magnetometer", "Latvia",
      "Drone survey over a WWII front-line field found a 250 kg bomb at 1.8 m.",
      {"shape": "sphere", "depth_top": 1.5, "size": 0.68, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.thedroningcompany.com/blog/revolutionizing-uxo-detection-drones-and-magnetometers-take-flight",
       "https://www.sphengineering.com/news/estimates-of-various-uxo-unexploded-ordnance-maximum-detection-distances-using-magnetometers"],
      ["Bomb as a sphere of equal volume (0.68 m), apparent susceptibility 3; sensor 2 m above ground."],
      {"sensor_height": 2.0, "gradiometer_height": 2.0}),
    S("F06", "4 m derinde 250 kg bomba, sensör 4 m yukarıda", "250 kg bomb buried 4 m, sensor 4 m above the seabed",
      "North Sea (German sector)", "Offshore wind UXO survey: 250 lb bombs, 2-4 m burial, sensor altitude 4 m.",
      {"shape": "sphere", "depth_top": 3.7, "size": 0.68, "material": "air", "host": "sand", "susceptibility_contrast": STEEL},
      ["https://www.openaccessgovernment.org/unexploded-ordnance-offshore-wind-farm/72642/"],
      ["As F05; seabed sediment as sand; sensor 4 m above the seabed."], {"sensor_height": 4.0, "gradiometer_height": 4.0}),
    S("F07", "Sığ küçük top mermisi (drone)", "Small artillery shell, shallow, drone at 2 m", "Central Spain",
      "Drone magnetometry at 2 m altitude detects small UXO with 2-18 nT anomalies.",
      {"shape": "sphere", "depth_top": 0.4, "size": 0.16, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.preprints.org/manuscript/202512.0511/download/final_file"],
      ["105 mm shell as a sphere of equal volume (0.16 m), apparent susceptibility 3."], {"sensor_height": 2.0, "gradiometer_height": 2.0}),
    S("F08", "Aynı mermi, yerde gradyometreyle", "Same shell, ground gradiometer", "Central Spain",
      "As F07, surveyed on foot with a fluxgate gradiometer.",
      {"shape": "sphere", "depth_top": 0.4, "size": 0.16, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.preprints.org/manuscript/202512.0511/download/final_file"], ["As F07."]),
    S("F09", "3 m derinde 50 kg bomba (yerde)", "50 kg bomb at 3 m, ground survey", "Central Germany",
      "Maximum detection distance tables for WWII bombs with magnetometers.",
      {"shape": "sphere", "depth_top": 3, "size": 0.4, "material": "air", "host": "soil", "susceptibility_contrast": STEEL},
      ["https://www.sphengineering.com/news/estimates-of-various-uxo-unexploded-ordnance-maximum-detection-distances-using-magnetometers"],
      ["50 kg bomb as a sphere of equal volume (0.4 m), apparent susceptibility 3."]),
]


def question(s: dict) -> str:
    t = s["target"]
    dims = {"sphere": lambda: f"about {t['size']:g} m across",
            "horizontal_cylinder": lambda: f"about {t['size']:g} m in diameter",
            "vertical_cylinder": lambda: f"about {t['size']:g} m across, extending to {t['depth_bottom']:g} m",
            "prism": lambda: f"about {t['size']:g} m by {t.get('length') or t['size']:g} m in plan, down to "
                             f"{t['depth_bottom']:g} m",
            "dyke": lambda: f"about {t['size']:g} m wide, extending to {t['depth_bottom']:g} m",
            "contact": lambda: f"with the offset unit extending from {t['depth_top']:g} m to {t['depth_bottom']:g} m",
            }[t["shape"]]()
    extra = ""
    if "sensor_height" in s["survey"]:
        extra = (f" The magnetic sensors (total-field and the lower gradiometer sensor) will be "
                 f"{s['survey']['sensor_height']:g} m above the ground.")
    return (f"Survey planning, {s['place']}. {s['setting']} The target ({s['title'].lower()}) has its top about "
            f"{t['depth_top']:g} m below the surface and is {dims}.{extra} Would a gravity survey, a total-field magnetic "
            "survey or a magnetic gradiometer survey detect it with standard field equipment? For each method, estimate "
            "the peak anomaly, say whether it is clearly detectable, marginal or not detectable, and recommend a station "
            "spacing.")


def build() -> tuple[list[dict], list[dict]]:
    from detectability import __version__, evaluate

    rows, out = [], []
    for s in SCENARIOS:
        r = evaluate(s["target"], s["survey"], methods=METHODS)
        res = {}
        for m in r.results:
            if not m.available:
                res[m.method] = {"available": False, "reason": m.reason}
                continue
            a = m.assessment
            res[m.method] = {"available": True, "peak": round(a.peak, 4), "units": a.units, "noise": round(a.noise, 4),
                             "snr": round(a.snr, 3), "verdict": a.verdict, "station_spacing": a.station_spacing}
        out.append({**s, "question": question(s), "reference": {"detectability": __version__, "methods": res,
                                                                "recommended": r.recommended}})
        row = {"id": s["id"], "title": s["title"], "place": s["place"], "recommended": r.recommended or "none"}
        for meth in METHODS:
            v = res[meth]
            row[meth] = f"{v['peak']:.3g} {v['units']} ({v['verdict']})" if v["available"] else "not assessed"
        rows.append(row)
    return out, rows


def main() -> int:
    out, rows = build()
    text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        same = (DATA / "scenarios.json").read_text("utf-8") == text
        print(f"{len(out)} scenarios; stored file", "matches" if same else "DIFFERS")
        return 0 if same else 1
    DATA.mkdir(exist_ok=True)
    (DATA / "scenarios.json").write_text(text, "utf-8")
    with (DATA / "reference.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "place", *METHODS, "recommended"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(out)} scenarios written to {DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
