import React, { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Shell } from "../components/Shell";
import { Toast, useToast } from "../components/Toast";
import { usePrefs } from "../lib/prefs";
import { sfx } from "../lib/sound";

export function Quiz() {
  const { token, user, loading } = useAuth();
  const { refresh } = usePrefs();
  const navigate = useNavigate();
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!token) return;
    api("/api/me/quiz", { token })
      .then(setQuestions)
      .catch(() => setQuestions([]));
  }, [token]);

  if (loading) {
    return (
      <Shell>
        <p className="pad">Loading...</p>
      </Shell>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  const current = questions[step];
  const answered = Object.keys(answers).length;

  async function submit() {
    setSaving(true);
    try {
      await api("/api/me/quiz", {
        method: "POST",
        token,
        body: {
          answers: Object.entries(answers).map(([question_id, choice]) => ({
            question_id,
            choice,
          })),
        },
      });
      await refresh();
      sfx.complete();
      navigate("/recommendations");
    } catch (err) {
      toast.say(err.message);
    } finally {
      setSaving(false);
    }
  }

  function pick(choiceId) {
    setAnswers((prev) => ({ ...prev, [current.id]: choiceId }));
    sfx.open();
    if (step < questions.length - 1) setStep(step + 1);
  }

  return (
    <Shell mascot="thinking">
      <section className="panel-head">
        <div>
          <p className="eyebrow">Taste quiz</p>
          <h1>Ten questions, then better picks</h1>
          <p className="lede">
            The answers seed your tag weights so For You has something to work with before you have
            rated anything. As real ratings arrive, the quiz quietly stops mattering.
          </p>
        </div>
        <span className="head-meta">
          {answered} of {questions.length || 10} answered
        </span>
      </section>

      {!current ? (
        <p className="pad">Loading questions...</p>
      ) : (
        <section className="quiz-card">
          <div className="quiz-progress" aria-hidden="true">
            {questions.map((q, i) => (
              <span key={q.id} className={i <= step ? "on" : ""} />
            ))}
          </div>
          <h2>{current.prompt}</h2>
          <div className="quiz-choices">
            {current.choices.map((choice) => (
              <button
                key={choice.id}
                type="button"
                className={`quiz-choice ${answers[current.id] === choice.id ? "active" : ""}`}
                onClick={() => pick(choice.id)}
              >
                {choice.label}
              </button>
            ))}
          </div>
          <div className="quiz-nav">
            <button
              type="button"
              className="ghost-btn"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              Back
            </button>
            <button
              type="button"
              className="ghost-btn"
              disabled={step >= questions.length - 1}
              onClick={() => setStep(step + 1)}
            >
              Skip
            </button>
            <button
              type="button"
              className="btn"
              disabled={answered === 0 || saving}
              onClick={submit}
            >
              {saving ? "Saving..." : `Use these ${answered} answers`}
            </button>
          </div>
        </section>
      )}
      <Toast message={toast.message} onDone={toast.clear} />
    </Shell>
  );
}
