import markdown
from weasyprint import HTML, CSS
import os

CSS_STYLE = """
@page {
    size: A4;
    margin: 14mm 16mm 14mm 16mm;
}
body {
    font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.35;
    color: #111;
}
h1 {
    font-size: 18pt;
    font-weight: 700;
    margin: 0 0 1px 0;
    line-height: 1.1;
}
h1 + p {
    font-size: 10pt;
    color: #444;
    margin: 0 0 4px 0;
}
h2 {
    font-size: 9.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #888;
    margin: 9px 0 4px 0;
    padding-bottom: 1px;
}
h3 {
    font-size: 9.5pt;
    font-weight: 700;
    margin: 6px 0 2px 0;
}
ul {
    margin: 2px 0 4px 0;
    padding-left: 14px;
}
li {
    margin-bottom: 2px;
}
p {
    margin: 2px 0 4px 0;
}
strong {
    font-weight: 700;
}
hr { display: none; }
"""

def make_pdf(rel_path):
    full_md = os.path.join(base, rel_path)
    content = open(full_md, encoding='utf-8').read()
    if '\n---\n' in content:
        content = content.split('\n---\n')[0].strip()
    html_body = markdown.markdown(content)
    html_full = '<html><head><meta charset="utf-8"></head><body>' + html_body + '</body></html>'
    pdf_path = os.path.join(os.path.dirname(full_md), 'cv.pdf')
    HTML(string=html_full).write_pdf(pdf_path, stylesheets=[CSS(string=CSS_STYLE)])
    return pdf_path

files = [
    # Today's batch
    '2026-06-15_1830_batch/01_ShipIn_Systems_Applied_CV_Researcher/cv.md',
    '2026-06-15_1830_batch/02_HARMAN_CV_Algorithm_Engineer/cv.md',
    '2026-06-15_1830_batch/03_CargoSeer_Senior_CV_Engineer/cv.md',
    # June 5 batch
    '2026-06-05_batch/01_Mobileye_DL_RD_Team_Lead/cv.md',
    '2026-06-05_batch/03_Mobileye_Vision_Localization_Algorithm_Engineer/cv.md',
    '2026-06-05_batch/04_Orbis_Computer_Vision_Engineer/cv.md',
    '2026-06-05_batch/05_Autobrains_Senior_CV_Engineer_Calibration/cv.md',
    '2026-06-05_batch/06_Camtek_CV_DL_Algorithm_Engineer_Senior/cv.md',
    '2026-06-05_batch/07_Camtek_AI_Engineer_CV_DL/cv.md',
    '2026-06-05_batch/08_Au10tix_Senior_Deep_Learning_Engineer/cv.md',
    '2026-06-05_batch/09_Mobileye_Algorithm_Researcher_CTO/cv.md',
    # June 6 first batch
    '2026-06-06_batch/02_GM_CV_Algorithm_Engineer_AV/cv.md',
    '2026-06-06_batch/03_GM_Perception_Insights_Engineer/cv.md',
    '2026-06-06_batch/04_Detect94_AI_Engineer_CV/cv.md',
    '2026-06-06_batch/05_Foresight_CV_Researcher/cv.md',
    '2026-06-06_batch/06_AWS_Sr_ML_Engineer_CV/cv.md',
    '2026-06-06_batch/07_Clarity_AI_ML_Engineer_CV/cv.md',
    # June 6 1200 batch
    '2026-06-06_1200_batch/01_UVeye_Senior-DL-Engineer/cv.md',
    '2026-06-06_1200_batch/02_Regulus_CV-Engineer-Drone-Interception/cv.md',
    '2026-06-06_1200_batch/03_UVeye_Senior-CV-Engineer/cv.md',
    '2026-06-06_1200_batch/04_Autobrains_Senior-DL-Engineer-Prediction-Policy/cv.md',
    '2026-06-06_1200_batch/05_Mentee_Robotics_Senior-SE-Edge-Inference/cv.md',
    # June 14 batch
    '2026-06-14_2012_batch/01_Imagen_Deep_Learning_Algorithm_Engineer/cv.md',
    '2026-06-14_2012_batch/02_Applied_Materials_Algorithm_Developer/cv.md',
]

base = '/home/danziv/projects/AutoJobApply/outputs'

for rel_path in files:
    make_pdf(rel_path)
    print(f'OK: {rel_path.split("/")[1]}')
