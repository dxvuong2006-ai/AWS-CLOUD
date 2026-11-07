import "../styles/management.css";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchLessonContent, fetchReviewDraft, approveReviewDraft } from "../api/review.api";

export default function LessonReviewPage() {
  const { lessonId } = useParams();
  const [lesson,setLesson]=useState(null);
  const [draft,setDraft]=useState(null);
  const [tab,setTab]=useState("summary");
  const [error,setError]=useState("");
  const [approved,setApproved]=useState(false);
  useEffect(()=>{
    Promise.all([fetchLessonContent(lessonId), fetchReviewDraft(lessonId)])
      .then(([lessonData,draftData])=>{setLesson(lessonData);setDraft(draftData);})
      .catch(e=>setError(e.detail||e.message));
  },[lessonId]);
  async function approve(){
    try{
      await approveReviewDraft(lessonId,{expected_revision:draft.expected_revision||draft.revision});
      setApproved(true);
    }catch(e){setError(e.detail||e.message);}
  }
  if(error)return <div className="page management-page"><p role="alert">{error}</p><Link to="/instructor/review-queue">Về hàng đợi</Link></div>;
  if(!lesson)return <div className="page management-page"><p>Đang tải...</p></div>;
  const transcript=lesson.transcript||[];
  const concepts=lesson.key_concepts||[];
  return <div className="page management-page">
    <div className="breadcrumb"><Link to="/instructor/review-queue">Hàng đợi AI</Link> / {lesson.title}</div>
    <div className="page-head"><div><h1>Kiểm duyệt học liệu AI</h1><p className="management-subtitle">{lesson.course_id?"Khóa học #"+lesson.course_id:""}</p></div><button className="btn-primary" onClick={approve} disabled={approved||!draft}>{approved?"Đã duyệt":"Duyệt lesson"}</button></div>
    {approved&&<p role="status" className="status-chip success">Lesson đã được phê duyệt.</p>}
    <div className="management-tabs"><button className={tab==="summary"?"active":""} onClick={()=>setTab("summary")}>Tóm tắt</button><button className={tab==="concepts"?"active":""} onClick={()=>setTab("concepts")}>Khái niệm</button><button className={tab==="flashcards"?"active":""} onClick={()=>setTab("flashcards")}>Flashcards</button><button className={tab==="transcript"?"active":""} onClick={()=>setTab("transcript")}>Transcript</button></div>
    <div className="review-layout"><aside className="review-panel"><h2>Nội dung video</h2>{transcript.map((line,index)=><div className="review-row" key={index}><strong>{line.start ?? index*5}s</strong><p>{line.text}</p></div>)}</aside><section className="review-panel">{tab==="summary"&&<><h2>Tóm tắt AI</h2><p>{lesson.summary||draft?.content?.summary||""}</p></>}{tab==="concepts"&&<><h2>Khái niệm</h2>{concepts.map((item,index)=><div className="review-row" key={index}>{typeof item==="string"?item:item.term}</div>)}</>}{tab==="flashcards"&&<><h2>Flashcards</h2>{(draft?.flashcards||[]).map((card,index)=><div className="review-row" key={`${card.position}-${index}`}><strong>{card.front}</strong><p>{card.back}</p></div>)}{(!draft?.flashcards?.length)&&<p>Chưa có flashcard trong bản nháp.</p>}</>}{tab==="transcript"&&<><h2>Transcript</h2>{transcript.map((line,index)=><p key={index}><strong>{line.start ?? index*5}s</strong> — {line.text}</p>)}</>}</section></div>
  </div>;
}
