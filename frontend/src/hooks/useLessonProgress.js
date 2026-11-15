import { useState, useEffect, useMemo } from "react";
import { fetchCourseProgress, saveLessonProgress, startViewingSession } from "../api/progress.api";
import { readSession } from "../api/session";
import { createSerialWriter } from "../utils/playback";
export function useLessonProgress(courseId, lessonId) {
  const [courseProgress,setCourseProgress]=useState(null), [loading,setLoading]=useState(true);
  const [error,setError]=useState(null), [saveError,setSaveError]=useState(null);
  const [retryVersion,setRetryVersion]=useState(0);
  const state=useMemo(()=>{
    const token=readSession()?.token;
    const current={active:false,latest:null,session:null,sequence:0};
    const checkAccount=()=>{if(!token || readSession()?.token!==token)throw new Error("Phiên đăng nhập đã thay đổi.");};
    current.start=()=>{
      checkAccount();
      if(!current.session)current.session=startViewingSession(lessonId,courseId).catch(err=>{current.session=null;throw err;});
      return current.session;
    };
    current.write=createSerialWriter(async payload=>{
      checkAccount();const session=await current.start();checkAccount();
      await saveLessonProgress(lessonId,{...payload,courseId,sessionId:session.id,sequence:++current.sequence});
      checkAccount();return fetchCourseProgress(courseId);
    });
    return current;
  },[courseId,lessonId]);
  useEffect(()=>{
    let active=true;state.active=true;setCourseProgress(null);setLoading(true);setError(null);setSaveError(null);
    fetchCourseProgress(courseId).then(data=>{if(active)setCourseProgress(data);})
      .catch(err=>{if(active)setError(err);}).finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;state.active=false;};
  },[courseId,state,retryVersion]);
  const save=async(position,duration,ranges)=>{
    const payload={lastPositionSeconds:position,durationSeconds:duration,watchedRanges:ranges.map(r=>[...r]),requestId:crypto.randomUUID()};
    state.latest=payload;
    try {
      const data=await state.write(payload);
      if(state.active){setCourseProgress(data);setSaveError(null);}
    }catch(err){if(state.active)setSaveError(err);}
  };
  const start=()=>{Promise.resolve().then(state.start).catch(err=>{if(state.active)setSaveError(err);});};
  const retry=()=>{const p=state.latest;if(p)save(p.lastPositionSeconds,p.durationSeconds,p.watchedRanges);};
  const current=courseProgress?.lessons.find(l=>String(l.lesson_id)===String(lessonId));
  return {courseProgress,loading,error,saveError,save,start,retry,reload:()=>setRetryVersion(v=>v+1),lastPosition:current?.last_position_seconds ?? 0};
}
