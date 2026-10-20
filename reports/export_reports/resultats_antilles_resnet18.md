# Essai court resnet18 - oiseaux des Antilles françaises

- Données : 4431 images, 31 espèces (train 3101 / val 665 / test 665)
- Réglages : resnet18, 3 époques, 1 époque de gel (freeze_epochs 1)
- Résultat test : accuracy 0.755 | top-3 0.904 | macro-F1 0.755

Baseline précédente (oiseaux européens, 40 espèces x 30 photos) :
accuracy 0.522 | top-3 0.739 | macro-F1 0.476
