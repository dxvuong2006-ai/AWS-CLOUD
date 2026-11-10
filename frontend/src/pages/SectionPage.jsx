import { useParams } from "react-router-dom";
import SectionGate from "../components/learning/SectionGate";
export default function SectionPage() {
  const { courseId, sectionId } = useParams();
  return <SectionGate key={`${courseId}:${sectionId}`} courseId={courseId} sectionId={sectionId} />;
}
