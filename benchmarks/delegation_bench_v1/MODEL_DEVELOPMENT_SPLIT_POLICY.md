# Model Development Split Policy

TRAIN uses Coding and Web seeds 0, 1, and 2. DEVELOPMENT uses Coding and Web seed 3. The MODEL-SELECTION-SEALED TEST uses Coding and Web seed 4.

Seed 4 has not been used for PIDR architecture selection, hyperparameter tuning, threshold calibration, aggregation selection, representation design, or model fitting.

Seed 4 is not described as never observed at the dataset level: Experiment 70 used the full benchmark for preregistered aggregate confirmatory measurement. This does not open its PIDR-v1 model-selection evaluation.

Once the PIDR-v1 sealed evaluation is opened, PIDR-v1 weights remain frozen; no hyperparameters change; no threshold changes may use seed-4 treatment outcomes; metrics will not be redefined; and there will be no second attempt at the same sealed test.
