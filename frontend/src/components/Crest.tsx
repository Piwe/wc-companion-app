interface Props {
  url: string | null | undefined;
  name: string | null | undefined;
  size?: number;
}

/** Team crest with a graceful fallback to the initials when no image is available. */
export default function Crest({ url, name, size = 24 }: Props) {
  const label = (name ?? "?").slice(0, 3).toUpperCase();
  if (!url) {
    return (
      <span
        className="inline-flex items-center justify-center rounded-full bg-slate-200 text-[10px] font-semibold text-slate-600"
        style={{ width: size, height: size }}
      >
        {label}
      </span>
    );
  }
  return (
    <img
      src={url}
      alt={name ?? "crest"}
      width={size}
      height={size}
      className="inline-block rounded-full object-contain"
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
      }}
    />
  );
}
