"""
ÉTAPE 2 — Fine-tuner un CNN pré-entraîné sur nos oiseaux.
Couvre le Bloc 05 : C1 (images -> tenseurs), C2 (comparer des architectures),
C3 (entraîner en optimisant une loss).

Usage (exemples) :
    python -m src.train_cnn --model resnet18 --epochs 12
    python -m src.train_cnn --model efficientnet_b0 --epochs 12
    python -m src.train_cnn --model convnext_tiny --epochs 12 --mlflow

Lance les 2-3 modèles avec les MÊMES réglages : c'est ta comparaison C2.
Résultats dans runs/<modèle>/ : best.pt, history.json, curves.png, confusion_matrix.png, metrics.json
"""
import argparse
import json
import random
import time
from pathlib import Path

import matplotlib
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

from src.common import IMAGENET_MEAN, IMAGENET_STD, IMG_SIZE, MODEL_NAMES, build_model, eval_transform

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def set_seed(seed):
    """Fixer les graines aléatoires = résultats reproductibles (important pour comparer)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_transform():
    """
    Augmentation de données : à chaque époque, la même photo est légèrement modifiée
    (recadrage, miroir, luminosité). Le modèle voit "plus" de variété et mémorise moins
    les images par cœur (= moins de surapprentissage / overfitting).
    """
    return transforms.Compose([
        transforms.RandomResizedCrop(IMG_SIZE, scale=(0.6, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def set_backbone_trainable(model, head, trainable):
    """Geler (False) ou dégeler (True) le corps du réseau. La tête reste toujours entraînable."""
    for p in model.parameters():
        p.requires_grad = trainable
    for p in head.parameters():
        p.requires_grad = True


def run_epoch(model, loader, criterion, device, k, optimizer=None):
    """
    Une époque = un passage complet sur toutes les images du loader.
    Si un optimizer est fourni -> mode ENTRAÎNEMENT (les poids sont mis à jour).
    Sinon -> mode ÉVALUATION (on mesure seulement, on ne touche pas aux poids).
    """
    training = optimizer is not None
    model.train(training)
    total_loss, correct, correct_topk, n = 0.0, 0, 0, 0
    with torch.set_grad_enabled(training):
        for x, y in loader:                      # un "batch" = un petit paquet d'images
            x, y = x.to(device), y.to(device)
            logits = model(x)                    # 1) le modèle prédit (scores par classe)
            loss = criterion(logits, y)          # 2) on mesure l'erreur (loss)
            if training:
                optimizer.zero_grad()            # 3) on remet les gradients à zéro
                loss.backward()                  # 4) rétropropagation : "qui est responsable de l'erreur ?"
                optimizer.step()                 # 5) on corrige légèrement les poids
            total_loss += loss.item() * x.size(0)
            top = logits.topk(k, dim=1).indices
            correct += (top[:, 0] == y).sum().item()
            correct_topk += (top == y.unsqueeze(1)).any(dim=1).sum().item()
            n += x.size(0)
    return total_loss / n, correct / n, correct_topk / n


@torch.no_grad()
def predict_all(model, loader, device):
    model.eval()
    y_true, y_pred = [], []
    for x, y in loader:
        y_pred += model(x.to(device)).argmax(1).cpu().tolist()
        y_true += y.tolist()
    return y_true, y_pred


def plot_curves(history, path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(history["train_loss"], label="train")
    axes[0].plot(history["val_loss"], label="validation")
    axes[0].set_title("Loss (plus bas = mieux)")
    axes[0].set_xlabel("époque")
    axes[0].legend()
    axes[1].plot(history["train_acc"], label="train")
    axes[1].plot(history["val_acc"], label="validation")
    axes[1].set_title("Accuracy")
    axes[1].set_xlabel("époque")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_confusion(y_true, y_pred, classes, path):
    cm = confusion_matrix(y_true, y_pred, labels=range(len(classes)), normalize="true")
    size = max(6, len(classes) * 0.28)
    fig, ax = plt.subplots(figsize=(size, size))
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes, rotation=90, fontsize=6)
    ax.set_yticklabels(classes, fontsize=6)
    ax.set_xlabel("espèce prédite")
    ax.set_ylabel("espèce réelle")
    fig.colorbar(im, fraction=0.046)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw", help="dossier avec 1 sous-dossier par espèce")
    ap.add_argument("--model", default="resnet18", choices=MODEL_NAMES)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--freeze_epochs", type=int, default=3,
                    help="époques où seule la dernière couche est entraînée (phase 1)")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3, help="learning rate de la phase 1")
    ap.add_argument("--patience", type=int, default=4, help="early stopping")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no_pretrained", action="store_true", help="(tests uniquement) pas de poids ImageNet")
    ap.add_argument("--mlflow", action="store_true", help="logger les expériences dans MLflow")
    ap.add_argument("--out", default="runs")
    args = ap.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(args.out) / args.model
    out.mkdir(parents=True, exist_ok=True)
    print(f"Appareil : {device} | modèle : {args.model}")

    # ---------- 1) DONNÉES : images -> tenseurs (Bloc 05 C1) ----------
    # ImageFolder lit data/raw/<espece>/*.jpg et utilise le nom du dossier comme étiquette.
    probe = datasets.ImageFolder(args.data)
    classes = probe.classes
    targets = probe.targets
    n_classes = len(classes)
    print(f"{len(targets)} images, {n_classes} espèces")

    # Découpage STRATIFIÉ 70 % train / 15 % validation / 15 % test (même proportion d'espèces partout)
    idx = list(range(len(targets)))
    train_idx, rest_idx = train_test_split(idx, test_size=0.30, stratify=targets, random_state=args.seed)
    rest_targets = [targets[i] for i in rest_idx]
    val_idx, test_idx = train_test_split(rest_idx, test_size=0.50, stratify=rest_targets, random_state=args.seed)

    # train : avec augmentation / val et test : sans aléatoire (on veut des mesures stables)
    train_ds = Subset(datasets.ImageFolder(args.data, transform=train_transform()), train_idx)
    val_ds = Subset(datasets.ImageFolder(args.data, transform=eval_transform()), val_idx)
    test_ds = Subset(datasets.ImageFolder(args.data, transform=eval_transform()), test_idx)
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch, num_workers=args.workers)
    test_loader = DataLoader(test_ds, batch_size=args.batch, num_workers=args.workers)
    print(f"train={len(train_ds)} | val={len(val_ds)} | test={len(test_ds)}")

    # ---------- 2) MODÈLE : transfer learning (Bloc 05 C2) ----------
    model, head = build_model(args.model, n_classes, pretrained=not args.no_pretrained)
    model.to(device)

    # ---------- 3) LOSS : la mesure d'erreur qu'on cherche à minimiser (Bloc 05 C3) ----------
    # CrossEntropyLoss = standard pour classer en plusieurs catégories.
    criterion = nn.CrossEntropyLoss()
    k = min(3, n_classes)

    if args.mlflow:
        import mlflow
        mlflow.set_experiment("birdsfinder-cnn")
        mlflow.start_run(run_name=args.model)
        mlflow.log_params({**vars(args), "n_classes": n_classes, "n_train": len(train_ds)})

    # ---------- 4) BOUCLE D'ENTRAÎNEMENT ----------
    # Phase 1 : on gèle le corps, on n'entraîne que la nouvelle tête (rapide, stable).
    # Phase 2 : on dégèle tout avec un learning rate 10x plus petit pour AFFINER (fine-tuning).
    history = {key: [] for key in ["train_loss", "train_acc", "val_loss", "val_acc", "val_topk"]}
    best_acc, best_epoch, bad_epochs = -1.0, 0, 0
    set_backbone_trainable(model, head, False)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    scheduler = None

    for epoch in range(args.epochs):
        if epoch == args.freeze_epochs:
            print(">>> Phase 2 : on dégèle tout le réseau (fine-tuning)")
            set_backbone_trainable(model, head, True)
            optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr / 10)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs - epoch))

        t0 = time.time()
        tr_loss, tr_acc, _ = run_epoch(model, train_loader, criterion, device, k, optimizer)
        va_loss, va_acc, va_topk = run_epoch(model, val_loader, criterion, device, k)
        if scheduler:
            scheduler.step()

        for key, val in zip(history, [tr_loss, tr_acc, va_loss, va_acc, va_topk]):
            history[key].append(val)
        print(f"époque {epoch + 1:2d}/{args.epochs} | train loss {tr_loss:.3f} acc {tr_acc:.3f} | "
              f"val loss {va_loss:.3f} acc {va_acc:.3f} top{k} {va_topk:.3f} | {time.time() - t0:.0f}s")
        if args.mlflow:
            mlflow.log_metrics({"train_loss": tr_loss, "train_acc": tr_acc, "val_loss": va_loss,
                                "val_acc": va_acc, "val_topk": va_topk}, step=epoch)

        # On garde le MEILLEUR modèle (sur la validation), pas forcément le dernier.
        if va_acc > best_acc:
            best_acc, best_epoch, bad_epochs = va_acc, epoch, 0
            torch.save({"state_dict": model.state_dict(), "classes": classes,
                        "model": args.model, "img_size": IMG_SIZE}, out / "best.pt")
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience and epoch >= args.freeze_epochs:
                print(f"Early stopping : plus d'amélioration depuis {args.patience} époques.")
                break

    # ---------- 5) ÉVALUATION FINALE sur le TEST (images jamais vues) ----------
    ckpt = torch.load(out / "best.pt", map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    te_loss, te_acc, te_topk = run_epoch(model, test_loader, criterion, device, k)
    y_true, y_pred = predict_all(model, test_loader, device)
    report = classification_report(y_true, y_pred, labels=range(n_classes),
                                   target_names=classes, output_dict=True, zero_division=0)
    metrics = {"model": args.model, "best_epoch": best_epoch + 1, "val_acc": best_acc,
               "test_loss": te_loss, "test_acc": te_acc, f"test_top{k}": te_topk,
               "macro_f1": report["macro avg"]["f1-score"], "n_classes": n_classes}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out / "history.json").write_text(json.dumps(history, indent=2))
    (out / "classification_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    plot_curves(history, out / "curves.png")
    plot_confusion(y_true, y_pred, classes, out / "confusion_matrix.png")
    if args.mlflow:
        mlflow.log_metrics({"test_acc": te_acc, f"test_top{k}": te_topk, "macro_f1": metrics["macro_f1"]})
        mlflow.log_artifacts(str(out))
        mlflow.end_run()
    print(f"\nTEST : accuracy {te_acc:.3f} | top{k} {te_topk:.3f} | macro-F1 {metrics['macro_f1']:.3f}")
    print(f"Fichiers dans {out}/")


if __name__ == "__main__":
    main()
