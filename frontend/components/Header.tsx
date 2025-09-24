import Image from "next/image";

export type HeaderProps = {
  className?: string;
};

export default function Header({ className = "" }: HeaderProps) {
  return (
    <div className={"w-full " + className}>
      <div className="flex flex-col items-center justify-center">
        <Image
          src={"/logo.png"}
          alt="Green smiski figure thinking."
          height={120}
          width={120}
        />
        <h1 className="text-3xl font-medium text-[var(--smiski-dark-green)]">
          Do You Have a Smiski?
        </h1>

        <p className="mt-3 text-xs text-zinc-500">
          Drag and drop images below to find out if they are smiskis or not.
        </p>
      </div>
    </div>
  );
}
