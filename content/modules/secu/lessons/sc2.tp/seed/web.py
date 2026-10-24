def render_comment(author, text):
    """Renvoie le HTML d'un commentaire."""
    return "<p><b>" + author + "</b>: " + text + "</p>"


def read_upload(base_dir, filename):
    """Renvoie le contenu du fichier filename, situé dans base_dir."""
    with open(base_dir + "/" + filename, encoding="utf-8") as f:
        return f.read()
