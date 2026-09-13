"""Deterministic math/statistics tool. No Gemma. No web."""
from __future__ import annotations
import re
from statistics import mean,median,multimode,pvariance,pstdev
NUM=r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
def nums(text):return [float(x) for x in re.findall(NUM,text)]
def clean(x):return int(x) if isinstance(x,float) and x.is_integer() else x
def analyze(text):
    low=text.lower(); n=nums(text)
    if "percentage" in low and " of " in low and len(n)>=2:
        if n[1]==0:raise ValueError("Division by zero.")
        v=n[0]/n[1]*100; return clean(v),f"{clean(v)}%"
    if "percent change" in low and len(n)>=2:
        if n[0]==0:raise ValueError("Original value cannot be zero.")
        v=(n[1]-n[0])/abs(n[0])*100; return clean(v),f"{clean(v)}%"
    if any(x in low for x in ("average","mean","median","mode","variance","standard deviation","range")) and n:
        if "median" in low:v=median(n)
        elif "mode" in low:v=multimode(n)
        elif "variance" in low:v=pvariance(n)
        elif "standard deviation" in low:v=pstdev(n)
        elif "range" in low:v=max(n)-min(n)
        else:v=mean(n)
        return v,str(clean(v))
    return None
