"""PDF cleaner/index-preprocessor for SAGE local knowledge."""
from pathlib import Path
import re,json

def clean_text(text):
    text=text.replace("\x00"," "); text=re.sub(r"-\n(?=\w)","",text); text=re.sub(r"[ \t]+"," ",text); text=re.sub(r"\n{3,}","\n\n",text); return text.strip()
def extract_pdf(path):
    from pypdf import PdfReader
    reader=PdfReader(str(path)); pages=[]
    for i,page in enumerate(reader.pages,1):
        text=clean_text(page.extract_text() or "")
        if text:pages.append({"page":i,"text":text})
    return pages
def build_document(pdf_path,output_dir):
    pages=extract_pdf(pdf_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); stem=Path(pdf_path).stem; chunks=[]
    for p in pages:
        lines=p["text"].splitlines(); section=""
        for line in lines:
            s=line.strip()
            if s and len(s)<120 and not s.endswith("."):section=s
        chunks.append({"source":Path(pdf_path).name,"page":p["page"],"section":section,"text":p["text"]})
    (out/(stem+".json")).write_text(json.dumps(chunks,ensure_ascii=False,indent=2),encoding="utf-8"); return len(chunks)
if __name__=="__main__":
    import sys
    if len(sys.argv)!=3:raise SystemExit("Usage: python3 pdf_processor.py input.pdf output_dir")
    print(build_document(sys.argv[1],sys.argv[2]))
