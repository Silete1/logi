CREATE TYPE shipment_status AS ENUM ('PENDING', 'IN_TRANSIT', 'AWAITING_CUSTOMS', 'CLEARED', 'DELIVERED');
CREATE TYPE container_type AS ENUM ('DRY', 'REEFER', 'OPEN_TOP', 'FLAT_RACK');
CREATE TYPE berth_status AS ENUM ('AVAILABLE', 'OCCUPIED', 'MAINTENANCE');

CREATE TABLE "client" (
    "client_id" SERIAL PRIMARY KEY,
    "company_name" VARCHAR(100) NOT NULL,
    "contact_person" VARCHAR(100) NOT NULL,
    "email" VARCHAR(100) NOT NULL UNIQUE,
    "phone_number" VARCHAR(50)
);

CREATE TABLE "vessel" (
    "vessel_id" SERIAL PRIMARY KEY,
    "vessel_name" VARCHAR(100) NOT NULL,
    "imo_number" VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE "yard_stack" (
    "yard_stack_id" SERIAL PRIMARY KEY,
    "location_code" VARCHAR(20) NOT NULL UNIQUE,
    "capacity" INTEGER NOT NULL
);

CREATE TABLE "ShipmentStatus" (
    "shipment_status_id" SERIAL PRIMARY KEY,
    "status_name" VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE "ContainerType" (
    "container_type_id" SERIAL PRIMARY KEY,
    "type_name" VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE "BerthStatus" (
    "berth_status_id" SERIAL PRIMARY KEY,
    "status_name" VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE "berth" (
    "berth_id" SERIAL PRIMARY KEY,
    "vessel_id" INTEGER UNIQUE,
    "berth_status_id" INTEGER NOT NULL,
    "berth_number" VARCHAR(10)
);

CREATE TABLE "shipment" (
    "shipment_id" SERIAL PRIMARY KEY,
    "client_id" INTEGER NOT NULL,
    "shipment_status_id" INTEGER NOT NULL,
    "bill_of_lading_no" VARCHAR(100) NOT NULL UNIQUE,
    "origin" VARCHAR(100) NOT NULL,
    "destination" VARCHAR(100) NOT NULL,
    "declared_value" DECIMAL(12, 2) NOT NULL
);

CREATE TABLE "customs_declaration" (
    "declaration_id" SERIAL PRIMARY KEY,
    "shipment_id" INTEGER NOT NULL UNIQUE,
    "declaration_date" DATE NOT NULL,
    "status" VARCHAR(50)
);

CREATE TABLE "container" (
    "container_id" SERIAL PRIMARY KEY,
    "shipment_id" INTEGER NOT NULL,
    "vessel_id" INTEGER,
    "yard_stack_id" INTEGER,
    "container_type_id" INTEGER NOT NULL,
    "container_number" VARCHAR(20) NOT NULL UNIQUE,
    "size" INTEGER NOT NULL
);

CREATE TABLE "truck" (
    "truck_id" SERIAL PRIMARY KEY,
    "container_id" INTEGER UNIQUE,
    "license_plate" VARCHAR(20) NOT NULL UNIQUE
);

ALTER TABLE "shipment" ADD CONSTRAINT "fk_shipment_client" FOREIGN KEY ("client_id") REFERENCES "client" ("client_id");
ALTER TABLE "shipment" ADD CONSTRAINT "fk_shipment_status" FOREIGN KEY ("shipment_status_id") REFERENCES "ShipmentStatus" ("shipment_status_id");
ALTER TABLE "customs_declaration" ADD CONSTRAINT "fk_customs_shipment" FOREIGN KEY ("shipment_id") REFERENCES "shipment" ("shipment_id");
ALTER TABLE "container" ADD CONSTRAINT "fk_container_shipment" FOREIGN KEY ("shipment_id") REFERENCES "shipment" ("shipment_id");
ALTER TABLE "container" ADD CONSTRAINT "fk_container_vessel" FOREIGN KEY ("vessel_id") REFERENCES "vessel" ("vessel_id");
ALTER TABLE "container" ADD CONSTRAINT "fk_container_yardstack" FOREIGN KEY ("yard_stack_id") REFERENCES "yard_stack" ("yard_stack_id");
ALTER TABLE "container" ADD CONSTRAINT "fk_container_type" FOREIGN KEY ("container_type_id") REFERENCES "ContainerType" ("container_type_id");
ALTER TABLE "berth" ADD CONSTRAINT "fk_berth_vessel" FOREIGN KEY ("vessel_id") REFERENCES "vessel" ("vessel_id");
ALTER TABLE "berth" ADD CONSTRAINT "fk_berth_status" FOREIGN KEY ("berth_status_id") REFERENCES "BerthStatus" ("berth_status_id");
ALTER TABLE "truck" ADD CONSTRAINT "fk_truck_container" FOREIGN KEY ("container_id") REFERENCES "container" ("container_id");
