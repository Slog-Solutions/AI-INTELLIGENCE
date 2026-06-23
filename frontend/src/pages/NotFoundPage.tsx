import { Link } from "react-router-dom";
import Icon from "../components/Icons";
import { BrandMark } from "../components/Ui";

export default function NotFoundPage() {
  return (
    <div className="not-found">
      <BrandMark />
      <div className="not-found__code">404</div>
      <span className="eyebrow">Navigation fault</span>
      <h1>Command route not found</h1>
      <p>The requested workspace does not exist or is outside your current access path.</p>
      <Link className="button button--primary" to="/dashboard"><Icon name="arrow" />Return to command</Link>
    </div>
  );
}
