package daemon

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	packages "github.com/antmicro/rdfm/daemon/packages"
)

var NotAuthorizedError = errors.New("Device did not provide authorization data, or the authorization has expired")

func (d *Device) checkUpdate() error {
	devType, err := d.rdfmCtx.GetCurrentDeviceType()
	if err != nil {
		return errors.New("Error getting current device type: " + err.Error())
	}
	swVer, err := d.rdfmCtx.GetCurrentArtifactName()
	if err != nil {
		return errors.New("Error getting current software version: " + err.Error())
	}
	metadata := map[string]string{
		"rdfm.hardware.devtype": devType,
		"rdfm.software.version": swVer,
		"rdfm.hardware.macaddr": d.macAddr,
	}
	log.Println("Metadata to check updates: ", metadata)

	serializedMetadata, err := json.Marshal(metadata)
	if err != nil {
		return errors.New("Failed to serialize metadata: " + err.Error())
	}
	endpoint := fmt.Sprintf("%s/api/v1/update/check",
		d.rdfmCtx.RdfmConfig.ServerURL)
	req, _ := http.NewRequest("POST", endpoint,
		bytes.NewBuffer(serializedMetadata),
	)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Add("Authorization", "Bearer token="+d.deviceToken)

	log.Println("Checking updates...")

	var client *http.Client
	client = &http.Client{Transport: d.httpTransport}
	res, err := client.Do(req)
	if err != nil {
		return errors.New("Update check request failed: " + err.Error())
	}
	defer res.Body.Close()

	switch res.StatusCode {
	case 200:
		log.Println("An update is available")
		var pkg packages.Package
		bodyBytes, err := io.ReadAll(res.Body)
		if err != nil {
			return errors.New("Failed to get package metadata from response body: " + err.Error())
		}
		err = json.Unmarshal(bodyBytes, &pkg)
		if err != nil {
			return errors.New("Failed to deserialize package metadata: " + err.Error())
		}

		log.Printf("Installing package from %s...\n", pkg.Uri)
		err = d.rdfmCtx.InstallArtifact(pkg.Uri)
		if err != nil {
			log.Println("Failed to install package",
				pkg.Id, err)
			// TODO: Do something in case of failure
		}
	case 204:
		log.Println("No updates are available")
	case 400:
		return errors.New("Device metadata is missing device type and/or software version")
	case 401:
		return NotAuthorizedError
	default:
		return errors.New("Unexpected status code from the server: " + res.Status)
	}
	return nil
}

func (d *Device) checkUpdatesPeriodically() {
	go func() {
		for {
			err := d.checkUpdate()
			if err == NotAuthorizedError {
				err = d.authenticateDeviceWithServer()
				if err == nil {
					continue
				}
				err = errors.New("Failed to autheniticate with the server: " + err.Error())
			}
			if err != nil {
				log.Println("Update check failed:", err)
			}
			updateDuration := time.Duration(d.rdfmCtx.RdfmConfig.UpdatePollIntervalSeconds) * time.Second
			log.Printf("Next update check in %s\n", updateDuration)
			time.Sleep(time.Duration(updateDuration))
		}
		log.Println("Stopped checking for updates")
	}()
}
