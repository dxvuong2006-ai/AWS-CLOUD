import { useState, useEffect, useCallback, useRef } from "react";
import { fetchLesson, fetchLessonVideo } from "../api/lessons.api";
export function useLesson(lessonId, courseId) {
  const [data,setData]=useState(null), [loading,setLoading]=useState(true), [error,setError]=useState(null);
  const [media,setMedia]=useState(null), [mediaError,setMediaError]=useState(null), [refreshing,setRefreshing]=useState(false);
  const [version,setVersion]=useState(0), [sourceVersion,setSourceVersion]=useState(0);
  const generation=useRef(0), inFlight=useRef(null), autoRetried=useRef(false);
  useEffect(()=>{
    const id=++generation.current; let active=true;
    setData(null);setMedia(null);setError(null);setMediaError(null);setLoading(true);setRefreshing(false);
    inFlight.current=null;autoRetried.current=false;setSourceVersion(0);
    fetchLesson(lessonId,courseId).then(async content=>{
      if(!active)return;
      setData(content);
      try { const url=await fetchLessonVideo(lessonId,courseId); if(active)setMedia(url); }
      catch(err){ if(active)setMediaError(err); }
    }).catch(err=>{if(active)setError(err);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{ active=false; if(generation.current===id)generation.current++; };
  },[lessonId,courseId,version]);
  const refreshVideo=useCallback(async()=>{
    if(inFlight.current)return inFlight.current;
    const id=generation.current;setRefreshing(true);
    const task=(async()=>{
      try {const url=await fetchLessonVideo(lessonId,courseId);
        if(generation.current===id){setMedia(url);setMediaError(null);setSourceVersion(v=>v+1);}
      } catch(err){if(generation.current===id)setMediaError(err);}
      finally {if(generation.current===id){setRefreshing(false);inFlight.current=null;}}
    })();
    inFlight.current=task;return task;
  },[lessonId,courseId]);
  useEffect(()=>{
    if(!media?.expiresAt)return;
    const wait=Math.min(2147483647,Math.max(1000,media.expiresAt-Date.now()-10000));
    const timer=setTimeout(refreshVideo,wait);return ()=>clearTimeout(timer);
  },[media,refreshVideo]);
  const onVideoError=()=>{
    if(!autoRetried.current){autoRetried.current=true;refreshVideo();}
    else setMediaError(new Error("Không phát được video. Hãy kiểm tra kết nối rồi thử lại."));
  };
  return {data,loading,error,media,mediaError,refreshing,sourceVersion,refreshVideo,onVideoError,reload:()=>setVersion(v=>v+1)};
}
