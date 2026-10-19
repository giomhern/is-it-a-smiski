import Image from "next/image";
import DragDropImageBox from "@/components/DragDropImageBox";
import Header from "@/components/Header";
import Icon, { BrandMark } from "@/components/Icon";

export default function Home() {
  return (
    <div className="site-shell">
      <a className="skip-link" href="#main">Skip to the photo test</a>
      <Header />
      <main id="main">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span className="little-dot" /> A collector’s little side project</p>
            <h1 id="hero-title">Small figure.<br /><em>Big mystery.</em></h1>
            <p className="hero-description">A tiny photo detective for your favorite<br className="desktop-break" /> glow-in-the-dark friends. Is it a Smiski?<br className="desktop-break" /> Let’s take a closer look.</p>
            <div className="collector-note">
              <span className="collector-image"><Image src="/examples/smiski.jpeg" alt="A little Smiski sitting with a laptop" width={72} height={72} /></span>
              <div><span className="handwritten">Made by a collector,</span><br /><span className="note-caption">for the curious ones.</span></div>
              <svg className="scribble" viewBox="0 0 75 45" fill="none" aria-hidden="true"><path d="M70 4C50 1 25 3 24 18c-2 14 20 20 25 6 6-16-28-15-43 12m0 0 3-11M6 36l13-1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            </div>
          </div>
          <div className="test-area">
            <p className="panel-caption"><Icon name="sparkle" size={14} /> One photo. One little guess.</p>
            <section className="test-panel" aria-labelledby="test-title">
              <div className="panel-heading"><h2 id="test-title">The Smiski test</h2><span className="panel-number">NO. 001</span></div>
              <DragDropImageBox className="legacy-upload" />
            </section>
            <p className="privacy-note"><span className="privacy-dot" /> Photos aren’t saved by this app. Just a look, then gone.</p>
          </div>
        </section>
        <section id="how-it-works" className="how-section" aria-labelledby="how-title">
          <div className="section-heading"><p className="eyebrow">A little peek behind the curtain</p><h2 id="how-title">Curiosity in. A little guess out.</h2></div>
          <div className="steps">
            <article><span className="step-number">01</span><h3>Bring a little mystery.</h3><p>Choose a photo from your camera roll, drop one in, or try an example.</p></article>
            <article><span className="step-number">02</span><h3>A second pair of eyes.</h3><p>A trained image model looks for the patterns it associates with Smiskis.</p></article>
            <article><span className="step-number">03</span><h3>A guess, with a grain of glow.</h3><p>It can get things wrong. This is a fun photo experiment, not an authenticity check.</p></article>
          </div>
          <a className="text-link" href="https://github.com/giomhern/is-it-a-smiski/blob/main/docs/MODEL_CARD.md">Meet the model & its limitations <Icon name="arrow" size={15} /></a>
        </section>
      </main>
      <footer className="site-footer"><span className="footer-brand"><BrandMark /> A small project with a soft spot for small things.</span><span>Unofficial. Unaffiliated. A little curious.</span></footer>
    </div>
  );
}
