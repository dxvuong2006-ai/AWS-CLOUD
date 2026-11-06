import { useEffect, useRef } from "react";
import { mergeWatchedRanges } from "../../utils/watchedRanges";
import { acceptedPlaybackRange } from "../../utils/playback";
import { PROGRESS_SAVE_INTERVAL_MS } from "../../config/learning";
export default function VideoPlayer({src,sourceVersion=0,onError,videoRef,onTimeUpdate,onProgress,onStart,startAt=0}) {
  const previous=useRef(null), ranges=useRef([]), lastSavedAt=useRef(0), resume=useRef(null), interacted=useRef(false);
  const callbacks=useRef({onProgress,onTimeUpdate,onStart});
  callbacks.current={onProgress,onTimeUpdate,onStart};
  const begin=(video)=>{
    previous.current=!video.paused && !video.seeking && !video.ended
      ? {position:video.currentTime,wallTime:performance.now(),rate:video.playbackRate}:null;
  };
  const record=(video)=>{
    const range=acceptedPlaybackRange(previous.current,video.currentTime,performance.now(),video.seeking);
    if(range)ranges.current=mergeWatchedRanges([...ranges.current,range],video.duration);
    begin(video);
  };
  const persist=(video)=>{
    if(!interacted.current || !Number.isFinite(video.duration) || video.duration<=0)return;
    lastSavedAt.current=performance.now();
    callbacks.current.onProgress?.(video.currentTime,video.duration,ranges.current.map(r=>[...r]));
  };
  useEffect(()=>{
    const video=videoRef.current;
    const flush=()=>{if(video){record(video);persist(video);}};
    const onHidden=()=>{if(document.visibilityState==="hidden")flush();};
    window.addEventListener("pagehide",flush);document.addEventListener("visibilitychange",onHidden);
    return ()=>{flush();window.removeEventListener("pagehide",flush);document.removeEventListener("visibilitychange",onHidden);};
  },[videoRef]);
  useEffect(()=>{if(sourceVersion>0)videoRef.current?.load();},[sourceVersion,videoRef]);
  return <div className="video-box"><video ref={videoRef} src={src} controls onError={onError}
    onEmptied={()=>{previous.current=null;}}
    onLoadedMetadata={event=>{
      const video=event.currentTarget;previous.current=null;lastSavedAt.current=performance.now();
      const position=resume.current ?? startAt;
      if(position>0 && position<video.duration)video.currentTime=position;
    }}
    onPlaying={event=>{interacted.current=true;callbacks.current.onStart?.();begin(event.currentTarget);}}
    onTimeUpdate={event=>{
      const video=event.currentTarget;if(video.readyState===0)return;
      record(video);resume.current=video.currentTime;callbacks.current.onTimeUpdate?.(video.currentTime);
      if(performance.now()-lastSavedAt.current>=PROGRESS_SAVE_INTERVAL_MS)persist(video);
    }}
    onSeeking={()=>{previous.current=null;}}
    onSeeked={event=>{resume.current=event.currentTarget.currentTime;begin(event.currentTarget);}}
    onRateChange={event=>{record(event.currentTarget);}}
    onWaiting={event=>{record(event.currentTarget);previous.current=null;}}
    onPause={event=>{record(event.currentTarget);previous.current=null;persist(event.currentTarget);}}
    onEnded={event=>{record(event.currentTarget);previous.current=null;persist(event.currentTarget);}}
  /></div>;
}
