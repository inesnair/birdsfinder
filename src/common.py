"""
Code partagé entre l'entraînement (02) et la prédiction (03).

Idée clé : le modèle doit recevoir À L'ENTRÉE EXACTEMENT les mêmes types d'images
qu'à l'entraînement (même taille, même normalisation). C'est pour ça qu'on garde
ces réglages au même endroit.
"""
import torch.nn as nn
from torchvision import models, transforms

# Les modèles pré-entraînés ont appris sur ImageNet (1,2 million d'images).
# Ils attendent des pixels normalisés avec ces moyennes / écarts-types.
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
IMG_SIZE = 224

MODEL_NAMES = ["resnet18", "resnet50", "efficientnet_b0", "convnext_tiny"]


def eval_transform():
    """Transformation appliquée en validation, test et prédiction (pas d'aléatoire)."""
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),                      # image -> tenseur (3, 224, 224), valeurs 0..1
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def build_model(name, n_classes, pretrained=True):
    """
    Charge un CNN pré-entraîné et remplace sa DERNIÈRE couche.

    - Le corps du réseau (backbone) sait déjà "voir" : bords, textures, formes...
    - La dernière couche d'origine prédit 1000 classes ImageNet. On la remplace par
      une couche qui prédit NOS n_classes espèces. C'est le "transfer learning".

    Retourne (modèle, tête) : la tête est la partie qu'on entraîne en premier.
    """
    weights = "DEFAULT" if pretrained else None
    if name == "resnet18":
        model = models.resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, n_classes)
        head = model.fc
    elif name == "resnet50":
        model = models.resnet50(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, n_classes)
        head = model.fc
    elif name == "efficientnet_b0":
        model = models.efficientnet_b0(weights=weights)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, n_classes)
        head = model.classifier
    elif name == "convnext_tiny":
        model = models.convnext_tiny(weights=weights)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, n_classes)
        head = model.classifier
    else:
        raise ValueError(f"Modèle inconnu : {name} (choix : {MODEL_NAMES})")
    return model, head
