import React from "react";
import { Route, Routes } from "react-router-dom";
import { Admin } from "./pages/Admin";
import { CollectionDetail, Collections } from "./pages/Collections";
import { Detail } from "./pages/Detail";
import { Discover } from "./pages/Discover";
import { Insights } from "./pages/Insights";
import { Login } from "./pages/Login";
import { Quiz } from "./pages/Quiz";
import { Recommendations } from "./pages/Recommendations";
import { Seasons } from "./pages/Seasons";
import { Settings } from "./pages/Settings";
import { Library, Shelf } from "./pages/Shelf";
import { Social } from "./pages/Social";
import { Watching } from "./pages/Watching";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Discover />} />
      <Route path="/watching" element={<Watching />} />
      <Route path="/recommendations" element={<Recommendations />} />
      <Route path="/collections" element={<Collections />} />
      <Route path="/collections/:id" element={<CollectionDetail />} />
      <Route path="/insights" element={<Insights />} />
      <Route path="/seasons" element={<Seasons />} />
      <Route path="/social" element={<Social />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/quiz" element={<Quiz />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/shelf" element={<Shelf />} />
      <Route path="/library" element={<Library />} />
      <Route path="/anime/:id" element={<Detail />} />
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<Discover />} />
    </Routes>
  );
}
