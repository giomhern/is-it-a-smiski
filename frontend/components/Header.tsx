import Link from "next/link";
import Icon, { BrandMark } from "@/components/Icon";

export default function Header() {
  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="Is it a Smiski? Home">
        <span className="brand-mark"><BrandMark /></span>
        <span>is it a smiski<span className="brand-question">?</span></span>
      </Link>
      <nav aria-label="Main navigation">
        <a className="how-link" href="#how-it-works">How it works</a>
        <a className="github-link" href="https://github.com/giomhern/is-it-a-smiski">View on GitHub <Icon name="arrow" size={16} /></a>
      </nav>
    </header>
  );
}
