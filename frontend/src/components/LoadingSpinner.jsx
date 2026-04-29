export default function LoadingSpinner() {
  return (
    <div className="spinner-overlay">
      <div className="spinner" />
      <p className="spinner-text">Generating your document...</p>
    </div>
  );
}
