import os
import re
import textstat
from flask import Flask, request, render_template
from docx import Document
from PyPDF2 import PdfReader

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Leitura dos arquivos
def ler_docx_texto(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def ler_pdf_texto(file_path):
    reader = PdfReader(file_path)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"
    return texto.strip()

# Score Final (ajustado com penalidades progressivas)
def calcular_score_final_bruto(score_bruto, flesch, topicos_por_paragrafo):
    score_final = score_bruto * 0.6

    if flesch < 30:
        score_final -= 10
    elif flesch < 50:
        score_final -= 5

    if topicos_por_paragrafo > 8:
        score_final -= 10
    elif topicos_por_paragrafo > 5:
        score_final -= 5

    return max(0, min(100, round(score_final, 2)))

# Detecção de características do texto
def detectar_caracteristicas(texto):
    frases = re.split(r'[.!?]', texto)
    frases = [f.strip() for f in frases if len(f.strip()) > 10]
    palavras = re.findall(r'\b\w+\b', texto)
    paragrafos = texto.count('\n\n') + 1
    palavras_total = len(palavras)

    topicos_excessivos = texto.count('\n- ') + texto.count('\n• ') + texto.count('\n* ')
    proporcao_topicos = topicos_excessivos / paragrafos if paragrafos > 0 else 0

    try:
        flesch = textstat.flesch_reading_ease(texto)
    except:
        flesch = 50

    score = 100
    relatorio = []

    if proporcao_topicos > 0.3:
        score -= 20
        relatorio.append("Uso excessivo de tópicos pode indicar estrutura gerada por IA.")
    
    if flesch > 70:
        score -= 15
        relatorio.append("Texto muito simples pode indicar baixa densidade técnica.")
    
    if len(frases) > 0 and sum(len(f.split()) for f in frases) / len(frases) < 10:
        score -= 15
        relatorio.append("Frases curtas e segmentadas indicam possível IA.")
    
    if palavras_total < 300:
        score -= 10
        relatorio.append("Texto muito curto para um laudo pericial completo.")

    score = max(score, 0)
    score_final = calcular_score_final_bruto(score, flesch, proporcao_topicos * 10)

    return score, score_final, relatorio, flesch, proporcao_topicos

# Rota principal
@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None
    relatorio = None
    flesch = None
    topicos = None
    score_final = None

    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if not arquivo:
            resultado = "Nenhum arquivo enviado."
        else:
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], arquivo.filename)
            arquivo.save(caminho)

            if arquivo.filename.endswith(".docx"):
                texto = ler_docx_texto(caminho)
            elif arquivo.filename.endswith(".pdf"):
                texto = ler_pdf_texto(caminho)
            else:
                resultado = "Formato inválido. Use .docx ou .pdf"
                return render_template("index.html", resultado=resultado)

            resultado, score_final, relatorio, flesch, topicos = detectar_caracteristicas(texto)

    return render_template(
        "index.html",
        resultado=resultado,
        score_final=score_final,
        relatorio=relatorio,
        flesch=flesch,
        topicos=round(topicos * 10, 2) if topicos else None
    )

if __name__ == "__main__":
    app.run(debug=True)
