import { Outlet } from "react-router-dom";
import BottomNav from "./BottomNav/BottomNav";
import "../App.css"

/** Wraps every logged-in screen: page content on top, bottom nav fixed below. */
export default function AppLayout() {
  return (
    <>
      <Outlet />
      <BottomNav />
    </>
  );
}