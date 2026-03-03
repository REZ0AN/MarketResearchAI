export default function Spinner({ full = false }) {
  const cls = full
    ? "fixed inset-0 flex items-center justify-center bg-[#1e1f20]"
    : "flex items-center justify-center p-4";
  return (
    <div className={cls}>
      <div className="w-8 h-8 rounded-full border-4 border-[#8ab4f8] border-t-transparent animate-spin" />
    </div>
  );
}