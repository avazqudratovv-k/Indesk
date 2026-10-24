import Footer from "./Footer";
import Navbar from "./Navbar";
import PageBackground from "./PageBackground";
import TabBar from "./TabBar";
import styles from "./Shell.module.css";

// Navbar on top, footer with the demo notice, and the tab bar on mobile. Wraps every route.
export default function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.shell}>
      <PageBackground />
      <Navbar />
      <div className={styles.content}>{children}</div>
      <Footer />
      <TabBar />
    </div>
  );
}
