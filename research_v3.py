"""Bounded, read-only web research for SAGE."""
from __future__ import annotations
import os, re, time, requests
from urllib.parse import urlparse, parse_qs

TAVILY_URL="https://api.tavily.com/search"
YOUTUBE_OEMBED="https://www.youtube.com/oembed"

class WebResearch:
    def __init__(self,max_rounds=2,results_per_search=4,max_sources=8,max_content_chars=9000,timeout=45,max_seconds=30):
        self.api_key=os.getenv("TAVILY_API_KEY")
        self.max_rounds=max_rounds; self.results_per_search=results_per_search
        self.max_sources=max_sources; self.max_content_chars=max_content_chars
        self.timeout=timeout; self.max_seconds=max_seconds
    def _search(self,q):
        if not self.api_key:return {"ok":False,"error":"Web research is not configured. Set TAVILY_API_KEY."}
        payload={"api_key":self.api_key,"query":q,"search_depth":"advanced","topic":"general","max_results":self.results_per_search,"include_answer":False,"include_raw_content":True}
        try:
            r=requests.post(TAVILY_URL,json=payload,timeout=self.timeout); r.raise_for_status(); d=r.json()
            return {"ok":True,"results":[{"title":x.get("title","").strip(),"url":x.get("url","").strip(),"content":(x.get("raw_content") or x.get("content") or "").strip()[:self.max_content_chars]} for x in d.get("results",[])]}
        except Exception as e:return {"ok":False,"error":f"Web search failed: {e}"}
    @staticmethod
    def youtube_id(url):
        try:
            p=urlparse(url); host=p.netloc.lower().replace("www.","")
            if host=="youtu.be":return p.path.strip("/").split("/")[0] or None
            if host in {"youtube.com","m.youtube.com"}:
                if p.path=="/watch":return parse_qs(p.query).get("v",[None])[0]
                for prefix in ("/shorts/","/embed/","/live/"):
                    if p.path.startswith(prefix):return p.path[len(prefix):].split("/")[0]
        except Exception:pass
        return None
    def youtube_metadata(self,url):
        vid=self.youtube_id(url)
        if not vid:return None
        canonical=f"https://www.youtube.com/watch?v={vid}"
        try:
            r=requests.get(YOUTUBE_OEMBED,params={"url":canonical,"format":"json"},timeout=15); r.raise_for_status(); d=r.json()
            return {"video_id":vid,"url":canonical,"title":d.get("title",""),"author":d.get("author_name","")}
        except Exception:return {"video_id":vid,"url":canonical,"title":"","author":""}
    def _dedupe(self,items):
        seen=set(); out=[]
        for x in items:
            k=x.get("url","").split("#")[0].rstrip("/").lower()
            if k and k not in seen:seen.add(k);out.append(x)
        return out[:self.max_sources]
    def _quality(self,url):
        h=urlparse(url).netloc.lower()
        if any(x in h for x in (".gov",".edu","nasa.gov","nvidia.com","google.com","microsoft.com","apple.com")):return 1.0
        if "youtube.com" in h or "youtu.be" in h:return .95
        if any(x in h for x in ("reuters.com","bbc.com","arstechnica.com","wikipedia.org")):return .85
        return .65
    def _score(self,results,direct=False,transcript=False):
        if not results and not direct and not transcript:return 0,"VERY LOW"
        score=20+(25 if direct else 0)+(15 if transcript else 0)+min(20,max(0,len(results)-1)*4)
        if results:score+=round(20*sum(self._quality(x["url"]) for x in results)/len(results))
        score=max(0,min(100,score)); level="VERY HIGH" if score>=90 else "HIGH" if score>=75 else "MEDIUM" if score>=50 else "LOW" if score>=25 else "VERY LOW"
        return score,level
    def youtube_transcript(self,vid):
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api=YouTubeTranscriptApi(); data=api.fetch(vid) if hasattr(api,"fetch") else YouTubeTranscriptApi.get_transcript(vid)
            return " ".join(getattr(x,"text",x.get("text","")) for x in data)[:12000]
        except Exception:return ""
    def research_url(self,url):
        start=time.monotonic(); meta=self.youtube_metadata(url) if self.youtube_id(url) else None
        transcript=self.youtube_transcript(meta["video_id"]) if meta else ""
        qs=[f'"{meta["title"]}"',f'"{meta["title"]}" official'] if meta and meta.get("title") else [f'"{url}"']
        results=[]
        for q in qs[:self.max_rounds]:
            if time.monotonic()-start>self.max_seconds:break
            r=self._search(q)
            if r.get("ok"):results.extend(r["results"])
        results=self._dedupe(results); score,level=self._score(results,bool(meta and meta.get("title")),bool(transcript))
        return {"ok":True,"type":"youtube" if meta else "url","metadata":meta or {},"transcript":transcript,"results":results,"evidence_score":score,"evidence_level":level}
    def research(self,query):
        start=time.monotonic(); first=self._search(query)
        if not first.get("ok"):return first
        results=first["results"]
        for q in [f'"{query}" independent sources',f'"{query}" official'][:max(0,self.max_rounds-1)]:
            if time.monotonic()-start>self.max_seconds:break
            r=self._search(q)
            if r.get("ok"):results.extend(r["results"])
        results=self._dedupe(results); score,level=self._score(results)
        return {"ok":True,"type":"research","results":results,"evidence_score":score,"evidence_level":level}
