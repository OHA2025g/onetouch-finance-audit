import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep console signal for debugging blank-screen cases.
    console.error("App render error:", error, info);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const msg = error?.message || String(error);
    return (
      <div className="p-8">
        <div className="crt-overline text-destructive">Application error</div>
        <div className="mt-2 max-w-[900px] rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-foreground">
          <div className="font-mono text-xs whitespace-pre-wrap">{msg}</div>
          <button
            type="button"
            className="crt-num mt-3 underline underline-offset-2"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}

