export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
      {message}
    </div>
  );
}
