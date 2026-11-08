/**
 * Google Calendar Dashboard Plugin
 *
 * Plain IIFE using the Hermes Plugin SDK globals. No build step, no imports.
 * Renders: status card, events list (next 14 days), create-event form.
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const {
    Card, CardHeader, CardTitle, CardContent,
    Badge, Button, Input, Label,
  } = SDK.components;
  const { useState, useEffect, useCallback } = SDK.hooks;
  const { cn, isoTimeAgo } = SDK.utils;

  const API = "/api/plugins/google-calendar";

  function usePlugin(url, deps) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const load = useCallback(function () {
      setLoading(true);
      setError(null);
      SDK.fetchJSON(url)
        .then(setData)
        .catch(function (err) {
          setError(err && err.message ? err.message : String(err));
        })
        .finally(function () { setLoading(false); });
    }, [url]);

    useEffect(function () {
      load();
    }, [load]);

    return { data, loading, error, reload: load };
  }

  function tzOffset() {
    const mins = -new Date().getTimezoneOffset();
    const sign = mins < 0 ? "-" : "+";
    const h = String(Math.floor(Math.abs(mins) / 60)).padStart(2, "0");
    const m = String(Math.abs(mins) % 60).padStart(2, "0");
    return sign + h + ":" + m;
  }

  // datetime-local value -> ISO 8601 with local offset.
  function toISO(localValue) {
    if (!localValue) return null;
    const pad = function (n) { return String(n).padStart(2, "0"); };
    const d = new Date(localValue);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + tzOffset();
  }

  function fmt(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      return d.toLocaleString();
    } catch (e) {
      return String(iso);
    }
  }

  function windowBounds() {
    const start = new Date();
    const end = new Date(start.getTime() + 14 * 24 * 60 * 60 * 1000);
    const pad = function (n) { return String(n).padStart(2, "0"); };
    const toLocal = function (d) {
      return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
        "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + tzOffset();
    };
    return { time_min: toLocal(start), time_max: toLocal(end) };
  }

  function StatusCard() {
    const s = usePlugin(API + "/status", []);
    const d = s.data;
    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement("div", { className: "flex items-center justify-between" },
          React.createElement(CardTitle, { className: "text-base" }, "Status"),
          React.createElement(Button, {
            onClick: s.reload,
            disabled: s.loading,
            className: cn(
              "inline-flex items-center gap-2 border border-border bg-background/40 px-3 py-1.5",
              "text-xs font-courier transition-colors hover:bg-foreground/10 cursor-pointer",
            ),
          }, s.loading ? "Refreshing..." : "Refresh"),
        ),
      ),
      React.createElement(CardContent, null,
        !d
          ? React.createElement("p", { className: "text-sm text-muted-foreground" }, s.error || "Loading...")
          : React.createElement("div", { className: "flex flex-col gap-2 text-sm" },
            React.createElement("div", { className: "flex items-center gap-2" },
              React.createElement(Badge, { variant: "outline" }, d.configured ? "configured" : "not configured"),
              d.calendar_id
                ? React.createElement(Badge, { variant: "outline" }, "calendar " + d.calendar_id)
                : null,
            ),
            d.configured
              ? React.createElement("p", { className: "text-xs text-muted-foreground" }, "Google Workspace OAuth is available.")
              : React.createElement("p", { className: "text-xs text-muted-foreground" }, d.hint || "Run google-workspace setup to authenticate."),
            d.error && d.configured
              ? React.createElement("p", { className: "text-xs text-muted-foreground" }, "best-effort: " + d.error)
              : null,
          ),
      ),
    );
  }

  function EventsCard({ onChanged }) {
    const bounds = windowBounds();
    const url = API + "/events?time_min=" + encodeURIComponent(bounds.time_min) +
      "&time_max=" + encodeURIComponent(bounds.time_max) + "&max_results=50";
    const s = usePlugin(url, []);
    const d = s.data;
    const events = (d && d.data) || [];

    function remove(ev) {
      if (!window.confirm("Delete calendar event \"" + (ev.summary || ev.id) + "\"?")) return;
      SDK.fetchJSON(API + "/events/" + encodeURIComponent(ev.id), { method: "DELETE" })
        .then(function () { onChanged(); s.reload(); })
        .catch(function (err) {
          alert((err && err.detail) ? err.detail : "Delete failed: " + (err && err.message ? err.message : String(err)));
        });
    }

    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement("div", { className: "flex items-center justify-between" },
          React.createElement(CardTitle, { className: "text-base" }, "Next 14 days"),
          React.createElement(Badge, { variant: "outline" }, String(events.length) + " events"),
        ),
      ),
      React.createElement(CardContent, null,
        !d
          ? React.createElement("p", { className: "text-sm text-muted-foreground" }, s.loading ? "Loading..." : (s.error || "No data"))
          : (d.error && !d.configured)
            ? React.createElement("p", { className: "text-sm text-muted-foreground" }, d.hint || d.error)
            : events.length === 0
              ? React.createElement("p", { className: "text-sm text-muted-foreground" }, "No upcoming events.")
              : React.createElement("div", { className: "flex flex-col gap-3" },
                  events.map(function (ev, i) {
                    return React.createElement("div", {
                      key: ev.id || i,
                      className: "flex items-start justify-between gap-3 border border-border p-3",
                    },
                      React.createElement("div", { className: "flex flex-col min-w-0" },
                        React.createElement("span", { className: "text-sm font-medium truncate" }, ev.summary || "(no title)"),
                        React.createElement("span", { className: "text-xs text-muted-foreground" },
                          fmt(ev.start) + " \u2192 " + fmt(ev.end)),
                        ev.location
                          ? React.createElement("span", { className: "text-xs text-muted-foreground" }, ev.location)
                          : null,
                      ),
                      React.createElement("div", { className: "flex items-center gap-2 shrink-0" },
                        ev.html_link
                          ? React.createElement("a", {
                              href: ev.html_link,
                              target: "_blank",
                              rel: "noreferrer",
                              className: "text-xs font-courier text-muted-foreground underline",
                            }, "open")
                          : null,
                        React.createElement(Button, {
                          onClick: function () { remove(ev); },
                          className: cn(
                            "border border-border bg-background/40 px-2 py-1",
                            "text-xs font-courier transition-colors hover:bg-foreground/10 cursor-pointer text-red-600",
                          ),
                        }, "Delete"),
                      ),
                    );
                  }),
                ),
      ),
    );
  }

  function CreateEvent({ onCreated }) {
    const [summary, setSummary] = useState("");
    const [start, setStart] = useState("");
    const [end, setEnd] = useState("");
    const [description, setDescription] = useState("");
    const [location, setLocation] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState(null);

    function submit() {
      setSubmitting(true);
      setResult(null);
      const body = {
        summary: summary,
        start: toISO(start),
        end: toISO(end),
        description: description || null,
        location: location || null,
      };
      SDK.fetchJSON(API + "/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
        .then(function () {
          setResult({ ok: true, message: "Event created." });
          setSummary(""); setStart(""); setEnd(""); setDescription(""); setLocation("");
          onCreated();
        })
        .catch(function (err) {
          setResult({ ok: false, message: (err && err.detail) ? err.detail : (err && err.message ? err.message : String(err)) });
        })
        .finally(function () { setSubmitting(false); });
    }

    function field(label, value, onChange, type) {
      return React.createElement("div", { className: "flex flex-col gap-1.5" },
        React.createElement(Label, { className: "text-sm font-medium" }, label),
        React.createElement(Input, {
          value: value,
          type: type || "text",
          onChange: function (e) { onChange(e.target.value); },
          className: "text-sm font-courier",
        }),
      );
    }

    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "text-base" }, "New event"),
      ),
      React.createElement(CardContent, { className: "flex flex-col gap-3" },
        field("Summary", summary, setSummary),
        React.createElement("div", { className: "grid grid-cols-2 gap-3" },
          field("Start", start, setStart, "datetime-local"),
          field("End", end, setEnd, "datetime-local"),
        ),
        field("Location (optional)", location, setLocation),
        field("Description (optional)", description, setDescription),
        React.createElement(Button, {
          onClick: submit,
          disabled: submitting || !summary.trim() || !start || !end,
          className: cn(
            "inline-flex items-center justify-center gap-2 border border-border bg-background/40 px-4 py-2",
            "text-sm font-courier transition-colors hover:bg-foreground/10 cursor-pointer",
            "disabled:opacity-40 disabled:cursor-not-allowed",
          ),
        }, submitting ? "Creating..." : "Create event"),
        result
          ? React.createElement("p", {
              className: cn("text-sm font-courier", result.ok ? "text-green-600" : "text-red-600"),
            }, result.message)
          : null,
      ),
    );
  }

  function CalendarPage() {
    const [refreshKey, setRefreshKey] = useState(0);
    const touch = useCallback(function () { setRefreshKey(function (n) { return n + 1; }); }, []);
    return React.createElement("div", { className: "flex flex-col gap-6" },
      React.createElement("div", { className: "flex items-center gap-3" },
        React.createElement(CardTitle, { className: "text-xl" }, "Google Calendar"),
        React.createElement(Badge, { variant: "outline" }, "v0.1.0"),
      ),
      React.createElement(StatusCard, null),
      React.createElement(EventsCard, { key: "events-" + refreshKey, onChanged: touch }),
      React.createElement(CreateEvent, { key: "create-" + refreshKey, onCreated: touch }),
    );
  }

  window.__HERMES_PLUGINS__.register("google-calendar", CalendarPage);
})();
