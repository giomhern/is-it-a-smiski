import Image from "next/image";
import DragDropImageBox from "@/components/DragDropImageBox";

export default function Home() {
  return (
    <main className="app">
      <header className="header">
        <Image
          src="/logo.png"
          alt="A green Smiski thinking"
          width={120}
          height={120}
          priority
        />
        <h1>Do You Have a Smiski?</h1>
        <p>Drag and drop a photo below to find out.</p>
      </header>
      <DragDropImageBox />
      <footer className="footer">
        <p>Photos aren’t saved. An unofficial project by a Smiski collector.</p>
        <a href="https://github.com/giomhern/is-it-a-smiski">GitHub</a>
        <span aria-hidden="true"> · </span>
        <a href="https://github.com/giomhern/is-it-a-smiski/blob/main/docs/MODEL_CARD.md">
          About the model
        </a>
      </footer>
    </main>
  );
}
