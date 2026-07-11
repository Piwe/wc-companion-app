import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Betting from "./pages/Betting";
import Group from "./pages/Group";
import Home from "./pages/Home";
import Match from "./pages/Match";
import Team from "./pages/Team";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/team/:id" element={<Team />} />
        <Route path="/group/:name" element={<Group />} />
        <Route path="/match/:id" element={<Match />} />
        <Route path="/betting" element={<Betting />} />
      </Routes>
    </Layout>
  );
}
