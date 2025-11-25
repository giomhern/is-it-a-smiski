import DragDropImageBox from "@/components/DragDropImageBox";
import Header from "@/components/Header";
import Image from "next/image";

export default function Home() {
  return (
    <div className="grid items-center justify-items-center min-h-screen p-8 pb-20 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <Header />
      <DragDropImageBox />
    </div>
  );
}
