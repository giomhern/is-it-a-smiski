"use client";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { motion, AnimatePresence } from "framer-motion";

export type DragDropImageBoxProps = {
  /** Callback when files pass validation */
  onFiles?: (files: File[]) => void;
  /** Accept list (MIME patterns or extensions). Example: ["image/*"] or [".png", ".jpg"] */
  accept?: string[];
  /** Maximum number of files a user may select */
  maxFiles?: number;
  /** Maximum single file size (MB) */
  maxSizeMB?: number;
  /** Optional className to style the outer box */
  className?: string;
  /** Start with these files already selected (e.g., from server) */
  initialFiles?: File[];
  /** Optional API URL (defaults to NEXT_PUBLIC_API_URL + /api/predict or relative /api/predict) */
  apiUrl?: string;
  /** Optional callback with server result */
  onResult?: (result: any) => void;
};

export default function DragDropImageBox({
  onFiles,
  accept = ["image/*"],
  maxFiles = 1,
  maxSizeMB = 10,
  className = "",
  initialFiles = [],
  apiUrl,
  onResult,
}: DragDropImageBoxProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [items, setItems] = useState<
    {
      id: string;
      file: File;
      url: string; // object URL
    }[]
  >([]);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  // bootstrap with initial files (no URLs available -> create them)
  useEffect(() => {
    if (initialFiles.length) {
      const seeded = initialFiles.slice(0, maxFiles).map((f, idx) => ({
        id: `${Date.now()}_${idx}_${f.name}`,
        file: f,
        url: URL.createObjectURL(f),
      }));
      setItems(seeded);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // cleanup object URLs
  useEffect(() => {
    return () => {
      items.forEach((it) => URL.revokeObjectURL(it.url));
    };
  }, [items]);

  const bytesLimit = useMemo(() => maxSizeMB * 1024 * 1024, [maxSizeMB]);

  const patternMatches = useCallback(
    (file: File) => {
      if (!accept || accept.length === 0) return true; // if nothing specified, accept all
      const lowerName = file.name.toLowerCase();
      return accept.some((rule) => {
        const r = rule.trim().toLowerCase();
        if (r === "image/*") return file.type.startsWith("image/");
        if (r.endsWith("/*")) {
          // e.g., video/*
          const prefix = r.slice(0, r.length - 1); // keep slash
          return file.type.toLowerCase().startsWith(prefix);
        }
        if (r.startsWith(".")) return lowerName.endsWith(r); // extension rule
        // Otherwise treat as exact mime type
        return file.type.toLowerCase() === r;
      });
    },
    [accept]
  );

  const validateFiles = useCallback(
    (list: File[]) => {
      const errs: string[] = [];

      // enforce max files
      const remainingSlots = Math.max(0, maxFiles - items.length);
      let limited = list.slice(0, remainingSlots);
      if (list.length > remainingSlots) {
        errs.push(
          `Only ${remainingSlots} more file${
            remainingSlots === 1 ? "" : "s"
          } allowed (max ${maxFiles}).`
        );
      }

      // type/size checks
      limited = limited.filter((file) => {
        if (!patternMatches(file)) {
          errs.push(`Unsupported type: ${file.name}`);
          return false;
        }
        if (file.size > bytesLimit) {
          const mb = (file.size / (1024 * 1024)).toFixed(1);
          errs.push(`${file.name} is ${mb}MB. Max ${maxSizeMB}MB.`);
          return false;
        }
        return true;
      });

      // filter duplicates by name+size
      const existingKey = new Set(
        items.map((it) => `${it.file.name}-${it.file.size}`)
      );
      const deduped = limited.filter(
        (f) => !existingKey.has(`${f.name}-${f.size}`)
      );
      if (deduped.length < limited.length) {
        errs.push("Some files were duplicates and skipped.");
      }

      setErrors(errs);
      return deduped;
    },
    [bytesLimit, items, maxFiles, maxSizeMB, patternMatches]
  );

  const addFiles = useCallback(
    (files: File[]) => {
      const valid = validateFiles(files);
      if (valid.length === 0) return;
      const newItems = valid.map((f) => ({
        id: `${Date.now()}_${f.name}`.replace(/\s+/g, "-"),
        file: f,
        url: URL.createObjectURL(f),
      }));
      setItems((prev) => {
        const next = [...prev, ...newItems].slice(0, maxFiles);
        return next;
      });
      onFiles?.(valid);
    },
    [maxFiles, onFiles, validateFiles]
  );

  const openFileDialog = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const onInputChange = useCallback<React.ChangeEventHandler<HTMLInputElement>>(
    (e) => {
      const list = Array.from(e.target.files || []);
      addFiles(list);
      e.currentTarget.value = ""; // reset so same file can be selected again
    },
    [addFiles]
  );

  const onDrop = useCallback<React.DragEventHandler<HTMLDivElement>>(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      // Prefer DataTransferItemList to filter directories in some browsers
      const incoming: File[] = [];
      const { items: dtItems, files } = e.dataTransfer;

      if (dtItems && dtItems.length) {
        for (let i = 0; i < dtItems.length; i++) {
          const it = dtItems[i];
          if (it.kind === "file") {
            const f = it.getAsFile();
            if (f) incoming.push(f);
          }
        }
      } else if (files && files.length) {
        for (let i = 0; i < files.length; i++) incoming.push(files[i]);
      }

      addFiles(incoming);
    },
    [addFiles]
  );

  const removeItem = useCallback((id: string) => {
    setItems((prev) => {
      const found = prev.find((p) => p.id === id);
      if (found) URL.revokeObjectURL(found.url);
      return prev.filter((p) => p.id !== id);
    });
  }, []);

  const boxVariants = {
    rest: { scale: 1, boxShadow: "0 0 0 0 rgba(0,0,0,0)" },
    hover: { scale: 1.01 },
    drag: { scale: 1.02, boxShadow: "0 10px 30px 0 rgba(0,0,0,0.08)" },
  } as const;

  const handlePredict = useCallback(async () => {
    if (items.length == 0) {
      setErrors(["No image to classify"]);
      return;
    }

    setErrors([]);
    setLoading(true);
    setResult(null);

    const file = items[0].file;
    const fd = new FormData();
    fd.append("image", file);

    const envBase =
      typeof process !== "undefined" &&
      process.env &&
      process.env.NEXT_PUBLIC_API_URL
        ? process.env.NEXT_PUBLIC_API_URL
        : "";
    const endpoint =
      (apiUrl && apiUrl.replace(/\/+$/, "")) ||
      (envBase ? `${envBase.replace(/\/+$/, "")}/api/predict` : "/api/predict");

    console.log("DragDropImageBox: predict endpoint ->", endpoint);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        body: fd,
      });

      const json = await res.json();

      if (!res.ok) {
        const err = json?.error || res.statusText || "Server error";
        throw new Error(err);
      }

      setResult(json);
      onResult?.(json);
    } catch (e: any) {
      setErrors([e?.message || "Failed to contact and connect to server."]);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, items, onResult]);

  return (
    <div className={"w-full " + className}>
      {/* Invisible native input */}
      <input
        ref={inputRef}
        type="file"
        accept={accept.join(",")}
        multiple={maxFiles > 1}
        className="hidden"
        onChange={onInputChange}
      />

      {/* Drop zone */}
      <motion.div
        role="button"
        tabIndex={0}
        aria-label="Upload images"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openFileDialog();
          }
        }}
        onClick={openFileDialog}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        initial="rest"
        animate={isDragging ? "drag" : "rest"}
        whileHover="hover"
        variants={boxVariants}
        className={[
          "relative flex flex-col items-center justify-center gap-3",
          "rounded-2xl border-2 border-dashed p-8 md:p-10",
          isDragging
            ? "border-indigo-500 bg-indigo-50/60"
            : "border-zinc-300 hover:border-zinc-400",
          "transition-colors cursor-pointer select-none",
        ].join(" ")}
      >
        <div className="pointer-events-none text-center">
          <p className="text-base font-medium">Drag & drop images here</p>
          <p className="text-sm text-zinc-500">
            or click to browse (max {maxFiles}, ≤ {maxSizeMB}MB each)
          </p>
        </div>

        <AnimatePresence>
          {isDragging && (
            <motion.div
              key="drag-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 rounded-2xl ring-2 ring-indigo-400/70"
            />
          )}
        </AnimatePresence>
      </motion.div>

      {/* Errors */}
      <AnimatePresence>
        {errors.length > 0 && (
          <motion.ul
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="mt-3 space-y-1 text-sm text-rose-600"
          >
            {errors.map((e, i) => (
              <li key={`${e}-${i}`}>• {e}</li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>

      {/* Preview grid */}
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {items.map((it) => (
          <motion.div
            key={it.id}
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="group relative overflow-hidden rounded-xl border border-zinc-200 bg-white"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={it.url}
              alt={it.file.name}
              className="h-40 w-full object-cover"
            />

            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/50 to-transparent p-2 text-xs text-white">
              <p className="truncate" title={it.file.name}>
                {it.file.name}
              </p>
            </div>

            <button
              type="button"
              onClick={() => removeItem(it.id)}
              className="absolute right-2 top-2 rounded-md bg-black/60 px-2 py-1 text-xs text-white opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100"
              aria-label={`Remove ${it.file.name}`}
            >
              Remove
            </button>
          </motion.div>
        ))}
      </div>

      <div className="mt-4 items-center">
        {items.length > 0 && (
          <div className="flex gap-1">
            <button
              onClick={handlePredict}
              disabled={loading}
              type="button"
              className="bg-indigo-600 text-white text-sm px-4 py-2 rounded disabled:opacity-60"
            >
              {loading ? "Classifying..." : "Classify Image"}
            </button>
            <button
              type="button"
              onClick={() => {
                // clear all
                items.forEach((it) => URL.revokeObjectURL(it.url));
                setItems([]);
                setErrors([]);
                setResult(null);
                onFiles?.([]);
              }}
              className="text-sm text-white bg-red-600 px-4 py-2 rounded"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Prediction result */}
      {result && (
        <div className="mt-4 p-3 rounded-lg bg-zinc-100/30 border border-zinc-300">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-zinc-500">Prediction</div>
              <div className="font-semibold">
                {result.prediction ??
                  (result.pred === 1 ? "Smiski" : "Non-Smiski")}
              </div>
              <div className="text-xs text-zinc-600">
                Confidence:{" "}
                {typeof result.confidence === "number"
                  ? `${(result.confidence * 100).toFixed(1)}%`
                  : result.probabilities
                  ? `${(result.probabilities.smiski * 100).toFixed(1)}%`
                  : ""}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Helper text */}
      <p className="mt-3 text-xs text-zinc-500">
        Accepted: {accept.join(", ") || "any"}. Tip: Ctrl/Cmd + V to open the
        browser file dialog.
      </p>
    </div>
  );
}
