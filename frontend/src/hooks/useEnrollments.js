import { useEffect, useState, useCallback } from "react";
import { fetchMyCourses } from "../api/enrollments.api";
export function useEnrollments() {
  const [data,setData] = useState([]), [loading,setLoading] = useState(true), [error,setError] = useState(null);
  const [version,setVersion] = useState(0);
  const reload = useCallback(() => setVersion(v=>v+1),[]);
  useEffect(() => {
    let active=true; setLoading(true); setError(null);
    fetchMyCourses().then(rows=>{if(active)setData(rows);}).catch(err=>{if(active)setError(err);})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[version]);
  return {data,loading,error,reload};
}
